from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Sequence

import yaml


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str], Path, float], CommandResult]


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


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tail(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[-limit:]


def collect_sympy_evidence(
    *,
    spec_path: str | Path,
    evidence_id: str,
    obligation: str,
    artifact: str | None = None,
) -> dict:
    """Run symbolic identity checks with SymPy.

    The spec is a trusted local research artifact. Expression strings are parsed
    by SymPy and must not be accepted from untrusted remote users.
    """
    import sympy as sp

    path = Path(spec_path).expanduser().resolve()
    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    try:
        raw = _load(path)
    except Exception as exc:
        raw = {}
        failures.append(f"could not load spec: {exc}")

    if not isinstance(raw, dict):
        failures.append("CAS spec root must be an object")
        raw = {}

    symbol_defs = raw.get("symbols", {})
    if not isinstance(symbol_defs, dict):
        failures.append("symbols must be an object")
        symbol_defs = {}

    local_dict: dict[str, Any] = {
        "I": sp.I,
        "pi": sp.pi,
        "E": sp.E,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "exp": sp.exp,
        "log": sp.log,
        "sqrt": sp.sqrt,
        "Abs": sp.Abs,
        "conjugate": sp.conjugate,
        "re": sp.re,
        "im": sp.im,
        "Derivative": sp.Derivative,
        "Function": sp.Function,
    }

    allowed_assumptions = {
        "real", "positive", "negative", "nonzero", "integer",
        "finite", "commutative", "complex",
    }
    for name, opts in symbol_defs.items():
        if opts is None:
            opts = {}
        if not isinstance(opts, dict):
            failures.append(f"symbol {name}: assumptions must be an object")
            continue
        unknown = set(opts) - allowed_assumptions
        if unknown:
            failures.append(
                f"symbol {name}: unsupported assumptions: {', '.join(sorted(unknown))}"
            )
            continue
        local_dict[str(name)] = sp.Symbol(str(name), **opts)

    checks = raw.get("checks", [])
    if not isinstance(checks, list) or not checks:
        failures.append("checks must be a non-empty list")
        checks = []

    methods = {
        "simplify": sp.simplify,
        "cancel": sp.cancel,
        "trigsimp": sp.trigsimp,
        "expand": sp.expand,
        "factor": sp.factor,
        "together": sp.together,
    }

    for index, item in enumerate(checks):
        row_failures: list[str] = []
        if not isinstance(item, dict):
            failures.append(f"check {index}: must be an object")
            continue
        check_id = str(item.get("id", f"check-{index}"))
        lhs_text = str(item.get("lhs", item.get("expression", "")))
        rhs_text = str(item.get("rhs", "0"))
        method_name = str(item.get("method", "simplify"))
        method = methods.get(method_name)
        if method is None:
            row_failures.append(f"unsupported method {method_name}")
            method = sp.simplify
        try:
            lhs = sp.sympify(lhs_text, locals=local_dict)
            rhs = sp.sympify(rhs_text, locals=local_dict)
            difference = lhs - rhs
            reduced = method(difference)
            passed = bool(reduced == 0)
            if not passed:
                eq = reduced.equals(0)
                passed = bool(eq is True)
            if not passed:
                row_failures.append("symbolic difference did not reduce to zero")
            reduced_text = str(reduced)
        except Exception as exc:
            passed = False
            reduced_text = ""
            row_failures.append(f"SymPy evaluation failed: {exc}")

        if row_failures:
            failures.extend(f"{check_id}: {x}" for x in row_failures)
        rows.append({
            "id": check_id,
            "lhs": lhs_text,
            "rhs": rhs_text,
            "method": method_name,
            "passed": passed,
            "reduced_difference": reduced_text,
            "failures": row_failures,
        })

    status = "PASS" if not failures else "FAIL"
    note = (
        f"SymPy symbolic audit passed {len(rows)} check(s)."
        if status == "PASS"
        else "SymPy symbolic audit failed: " + failures[0]
    )
    return {
        "id": evidence_id,
        "obligation": obligation,
        "status": status,
        "engine": "sympy",
        "artifact": artifact or str(path),
        "note": note,
        "metadata": {
            "adapter": "theorygate.adapters.cas.sympy",
            "sympy_version": sp.__version__,
            "spec": str(path),
            "spec_sha256": _sha256(path) if path.is_file() else None,
            "checks": rows,
            "failures": failures,
            "security_note": "SymPy specs are trusted local inputs; expression parsing is not a sandbox.",
        },
    }


@dataclass(frozen=True)
class ExternalCASConfig:
    engine: str
    script: Path
    evidence_id: str
    obligation: str
    executable: str | None = None
    pass_marker: str = "THEORYGATE:PASS"
    fail_marker: str = "THEORYGATE:FAIL"
    timeout: float = 600.0
    artifact: str | None = None


def collect_external_cas_evidence(
    config: ExternalCASConfig,
    *,
    runner: CommandRunner = _default_runner,
) -> dict:
    """Run an xAct/Wolfram or Cadabra audit script under a marker contract.

    The script itself performs the domain-specific tensor/canonicalization checks.
    TheoryGate verifies process success plus an explicit PASS marker and records
    exact script/tool provenance.
    """
    engine = config.engine.lower()
    if engine not in {"xact", "cadabra"}:
        raise ValueError("external CAS engine must be xact or cadabra")

    script = Path(config.script).expanduser().resolve()
    cwd = script.parent
    failures: list[str] = []

    if engine == "xact":
        executable = config.executable or "wolframscript"
        command = (executable, "-file", str(script))
        version_command = (executable, "--version")
    else:
        executable = config.executable or "cadabra2"
        command = (executable, str(script))
        version_command = (executable, "--version")

    version_r = runner(version_command, cwd, config.timeout)
    run_r = runner(command, cwd, config.timeout)
    combined = "\n".join(x for x in (run_r.stdout, run_r.stderr) if x)

    if version_r.returncode != 0:
        failures.append(f"{engine} version check failed with exit code {version_r.returncode}")
    if run_r.returncode != 0:
        failures.append(f"{engine} audit script exited {run_r.returncode}")
    if config.fail_marker and config.fail_marker in combined:
        failures.append(f"{engine} script emitted explicit failure marker")
    if config.pass_marker not in combined:
        failures.append(f"{engine} script did not emit required pass marker {config.pass_marker!r}")

    status = "PASS" if not failures else "FAIL"
    version_text = (version_r.stdout or version_r.stderr).strip()
    note = (
        f"{engine} external symbolic audit passed."
        if status == "PASS"
        else f"{engine} external symbolic audit failed: {failures[0]}"
    )
    return {
        "id": config.evidence_id,
        "obligation": config.obligation,
        "status": status,
        "engine": engine,
        "artifact": config.artifact or str(script),
        "note": note,
        "metadata": {
            "adapter": f"theorygate.adapters.cas.{engine}",
            "script": str(script),
            "script_sha256": _sha256(script) if script.is_file() else None,
            "tool_version": version_text or None,
            "version_command": list(version_command),
            "command": list(command),
            "returncode": run_r.returncode,
            "pass_marker": config.pass_marker,
            "fail_marker": config.fail_marker,
            "stdout_tail": _tail(run_r.stdout),
            "stderr_tail": _tail(run_r.stderr),
            "failures": failures,
            "contract_note": (
                "TheoryGate checks execution provenance and markers; the script is "
                "responsible for the domain-specific xAct/Cadabra symbolic assertions."
            ),
        },
    }


def write_evidence_json(evidence: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
