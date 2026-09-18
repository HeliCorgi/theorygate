from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str], Path, float], CommandResult]


@dataclass(frozen=True)
class LeanEvidenceConfig:
    project: Path
    evidence_id: str
    obligation: str
    imports: tuple[str, ...]
    theorems: tuple[str, ...]
    build_targets: tuple[str, ...] = ()
    allow_axioms: tuple[str, ...] | None = None
    forbid_axioms: tuple[str, ...] = ("sorryAx",)
    allow_dirty: bool = False
    timeout: float = 600.0
    artifact: str | None = None


_AXIOMS_RE = re.compile(
    r"'([^']+)'\s+depends on axioms:\s*\[([^\]]*)\]",
    flags=re.MULTILINE,
)
_NO_AXIOMS_RE = re.compile(
    r"'([^']+)'\s+does not depend on any axioms",
    flags=re.MULTILINE,
)


def _default_runner(command: Sequence[str], cwd: Path, timeout: float) -> CommandResult:
    cmd = tuple(str(x) for x in command)
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(cmd, proc.returncode, proc.stdout, proc.stderr)
    except FileNotFoundError as exc:
        return CommandResult(cmd, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(cmd, 124, out, (err + f"\ntimeout after {timeout}s").strip())


def parse_axioms_output(text: str) -> dict[str, list[str]]:
    """Parse Lean 4 `#print axioms` messages.

    Lean normally emits one of:

      'Foo.bar' depends on axioms: [propext, Classical.choice, Quot.sound]
      'Foo.bar' does not depend on any axioms

    The parser intentionally does not infer trust from axiom names. It only
    records them; policy is applied separately.
    """
    result: dict[str, list[str]] = {}
    for match in _AXIOMS_RE.finditer(text):
        raw = match.group(2).strip()
        axioms = [] if not raw else [x.strip() for x in raw.split(",") if x.strip()]
        result[match.group(1)] = axioms
    for match in _NO_AXIOMS_RE.finditer(text):
        result[match.group(1)] = []
    return result


def _tail(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[-limit:]


def _first_line(result: CommandResult) -> str | None:
    if result.returncode != 0:
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _project_hashes(project: Path) -> dict[str, str]:
    names = (
        "lean-toolchain",
        "lake-manifest.json",
        "lakefile.lean",
        "lakefile.toml",
    )
    out: dict[str, str] = {}
    for name in names:
        p = project / name
        if p.is_file():
            out[name] = _sha256(p)
    return out


def _audit_source(imports: tuple[str, ...], theorem: str) -> str:
    lines = [f"import {module}" for module in imports]
    lines += ["", f"#check {theorem}", f"#print axioms {theorem}", ""]
    return "\n".join(lines)


def _git_value(
    runner: CommandRunner,
    project: Path,
    timeout: float,
    *args: str,
) -> CommandResult:
    return runner(("git", *args), project, timeout)


def _artifact_id(
    project: Path,
    remote: str | None,
    commit: str | None,
    git_root: Path | None,
) -> str:
    if remote and commit:
        rel = "."
        if git_root is not None:
            try:
                rel = str(project.resolve().relative_to(git_root.resolve()))
            except ValueError:
                rel = str(project)
        return f"{remote}@{commit}:{rel}"
    return str(project)


def collect_lean_evidence(
    config: LeanEvidenceConfig,
    *,
    runner: CommandRunner = _default_runner,
) -> dict:
    """Execute a Lean project audit and return one TheoryGate evidence record.

    PASS means, at the recorded scope:
      * the project is identified by a clean git commit;
      * `lake build [targets...]` succeeded;
      * every requested theorem resolved under the requested imports;
      * `#print axioms` output was parsed for every theorem;
      * no forbidden axiom was present;
      * if an allow-list was supplied, every reported axiom was on it.

    A dirty tree is FAIL by default because the commit SHA would not identify
    the compiled source. With `allow_dirty=True`, collection proceeds but the
    result is PARTIAL rather than PASS.
    """
    project = Path(config.project).expanduser().resolve()
    failures: list[str] = []
    warnings: list[str] = []

    if not project.is_dir():
        failures.append(f"project directory does not exist: {project}")

    # Git provenance. We collect as much as possible even if one query fails.
    commit_r = _git_value(runner, project, config.timeout, "rev-parse", "HEAD")
    commit = _first_line(commit_r)
    if not commit:
        failures.append("could not resolve git commit SHA")

    root_r = _git_value(runner, project, config.timeout, "rev-parse", "--show-toplevel")
    root_text = _first_line(root_r)
    git_root = Path(root_text) if root_text else None

    branch_r = _git_value(
        runner, project, config.timeout, "rev-parse", "--abbrev-ref", "HEAD"
    )
    branch = _first_line(branch_r)

    status_r = _git_value(runner, project, config.timeout, "status", "--porcelain")
    dirty = status_r.returncode != 0 or bool(status_r.stdout.strip())
    if status_r.returncode != 0:
        failures.append("could not inspect git working-tree status")
    elif dirty and not config.allow_dirty:
        failures.append("git working tree is dirty; commit SHA does not identify compiled source")
    elif dirty:
        warnings.append("git working tree is dirty; evidence is downgraded to PARTIAL")

    remote_r = _git_value(runner, project, config.timeout, "remote", "get-url", "origin")
    remote = _first_line(remote_r)

    lake_version_r = runner(("lake", "--version"), project, config.timeout)
    lean_version_r = runner(("lake", "env", "lean", "--version"), project, config.timeout)
    lake_version = _first_line(lake_version_r)
    lean_version = _first_line(lean_version_r)
    if lake_version_r.returncode != 0:
        failures.append("lake executable/version check failed")
    if lean_version_r.returncode != 0:
        failures.append("lean version check through lake env failed")

    build_command = ("lake", "build", *config.build_targets)
    build_r = runner(build_command, project, config.timeout)
    if build_r.returncode != 0:
        failures.append(f"lake build failed with exit code {build_r.returncode}")

    theorem_rows: list[dict] = []
    allow_set = None if config.allow_axioms is None else set(config.allow_axioms)
    forbid_set = set(config.forbid_axioms)

    if build_r.returncode == 0:
        for theorem in config.theorems:
            with tempfile.TemporaryDirectory(prefix="theorygate-lean-") as td:
                audit_path = Path(td) / "TheoryGateAudit.lean"
                audit_path.write_text(
                    _audit_source(config.imports, theorem),
                    encoding="utf-8",
                )
                audit_r = runner(
                    ("lake", "env", "lean", str(audit_path)),
                    project,
                    config.timeout,
                )
            combined = "\n".join(x for x in (audit_r.stdout, audit_r.stderr) if x)
            parsed = parse_axioms_output(combined)
            axioms = parsed.get(theorem)
            row_failures: list[str] = []

            if audit_r.returncode != 0:
                row_failures.append(f"Lean audit exited {audit_r.returncode}")
            if axioms is None:
                row_failures.append("#print axioms output was not parsed for theorem")
                axioms = []

            forbidden = sorted(set(axioms) & forbid_set)
            unexpected = (
                []
                if allow_set is None
                else sorted(set(axioms) - allow_set)
            )
            if forbidden:
                row_failures.append(
                    "forbidden axioms: " + ", ".join(forbidden)
                )
            if unexpected:
                row_failures.append(
                    "axioms outside allow-list: " + ", ".join(unexpected)
                )

            if row_failures:
                failures.extend(f"{theorem}: {x}" for x in row_failures)

            theorem_rows.append(
                {
                    "name": theorem,
                    "axioms": axioms,
                    "forbidden_axioms_found": forbidden,
                    "unexpected_axioms": unexpected,
                    "returncode": audit_r.returncode,
                    "stdout_tail": _tail(audit_r.stdout),
                    "stderr_tail": _tail(audit_r.stderr),
                }
            )

    if failures:
        status = "FAIL"
    elif dirty:
        status = "PARTIAL"
    else:
        status = "PASS"

    artifact = config.artifact or _artifact_id(project, remote, commit, git_root)
    short_commit = commit[:12] if commit else "unknown"
    if status == "PASS":
        note = (
            f"Lean build and axiom audit passed for {len(config.theorems)} theorem(s) "
            f"at git commit {short_commit}."
        )
    elif status == "PARTIAL":
        note = (
            f"Lean build/audit completed at {short_commit}, but provenance is partial: "
            + "; ".join(warnings)
        )
    else:
        note = "Lean evidence gate failed: " + (failures[0] if failures else "unknown failure")

    return {
        "id": config.evidence_id,
        "obligation": config.obligation,
        "status": status,
        "engine": "lean",
        "artifact": artifact,
        "note": note,
        "metadata": {
            "adapter": "theorygate.adapters.lean",
            "project": str(project),
            "git": {
                "commit": commit,
                "branch": branch,
                "dirty": dirty,
                "remote": remote,
                "root": None if git_root is None else str(git_root),
            },
            "toolchain": {
                "lake_version": lake_version,
                "lean_version": lean_version,
                "file_sha256": _project_hashes(project) if project.is_dir() else {},
            },
            "build": {
                "command": list(build_command),
                "targets": list(config.build_targets),
                "returncode": build_r.returncode,
                "stdout_tail": _tail(build_r.stdout),
                "stderr_tail": _tail(build_r.stderr),
            },
            "audit": {
                "imports": list(config.imports),
                "theorems": theorem_rows,
                "allow_axioms": (
                    None if config.allow_axioms is None else list(config.allow_axioms)
                ),
                "forbid_axioms": list(config.forbid_axioms),
                "allow_dirty": config.allow_dirty,
            },
            "failures": failures,
            "warnings": warnings,
        },
    }


def write_evidence_json(evidence: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
