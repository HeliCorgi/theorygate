import tempfile
import unittest
from pathlib import Path
import re

from theorygate.adapters.lean import (
    CommandResult,
    LeanEvidenceConfig,
    collect_lean_evidence,
    parse_axioms_output,
)


class FakeRunner:
    def __init__(
        self,
        *,
        dirty=False,
        build_returncode=0,
        theorem_axioms=None,
        theorem_returncode=0,
    ):
        self.dirty = dirty
        self.build_returncode = build_returncode
        self.theorem_axioms = theorem_axioms or {}
        self.theorem_returncode = theorem_returncode
        self.commands = []

    def __call__(self, command, cwd, timeout):
        cmd = tuple(command)
        self.commands.append(cmd)
        if cmd == ("git", "rev-parse", "HEAD"):
            return CommandResult(cmd, 0, "0123456789abcdef0123456789abcdef01234567\n", "")
        if cmd == ("git", "rev-parse", "--show-toplevel"):
            return CommandResult(cmd, 0, str(Path(cwd).parent) + "\n", "")
        if cmd == ("git", "rev-parse", "--abbrev-ref", "HEAD"):
            return CommandResult(cmd, 0, "main\n", "")
        if cmd == ("git", "status", "--porcelain"):
            return CommandResult(cmd, 0, " M Formal/Test.lean\n" if self.dirty else "", "")
        if cmd == ("git", "remote", "get-url", "origin"):
            return CommandResult(cmd, 0, "https://github.com/example/physics.git\n", "")
        if cmd == ("lake", "--version"):
            return CommandResult(cmd, 0, "Lake version 5.0.0\n", "")
        if cmd == ("lake", "env", "lean", "--version"):
            return CommandResult(cmd, 0, "Lean (version 4.20.0)\n", "")
        if cmd[:2] == ("lake", "build"):
            return CommandResult(cmd, self.build_returncode, "build output\n", "")
        if cmd[:3] == ("lake", "env", "lean"):
            source = Path(cmd[-1]).read_text(encoding="utf-8")
            theorem = re.search(r"#print axioms ([^\s]+)", source).group(1)
            axioms = self.theorem_axioms.get(theorem, [])
            if axioms:
                out = f"'{theorem}' depends on axioms: [{', '.join(axioms)}]\n"
            else:
                out = f"'{theorem}' does not depend on any axioms\n"
            return CommandResult(cmd, self.theorem_returncode, out, "")
        raise AssertionError(f"unexpected command: {cmd}")


class LeanEvidenceAdapterTests(unittest.TestCase):
    def make_project(self):
        td = tempfile.TemporaryDirectory()
        project = Path(td.name) / "lean"
        project.mkdir()
        (project / "lean-toolchain").write_text("leanprover/lean4:v4.20.0\n")
        (project / "lakefile.toml").write_text('name = "fixture"\n')
        return td, project

    def config(self, project, **kwargs):
        base = dict(
            project=project,
            evidence_id="lean-proof",
            obligation="FORMAL_IDENTITY",
            imports=("PhysicsAudit",),
            theorems=("PhysicsAudit.factorization",),
        )
        base.update(kwargs)
        return LeanEvidenceConfig(**base)

    def test_parse_axioms_output(self):
        text = (
            "'A.foo' depends on axioms: [propext, Classical.choice, Quot.sound]\n"
            "'A.bar' does not depend on any axioms\n"
        )
        self.assertEqual(
            parse_axioms_output(text),
            {
                "A.foo": ["propext", "Classical.choice", "Quot.sound"],
                "A.bar": [],
            },
        )

    def test_clean_build_and_audit_yields_pass(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        runner = FakeRunner(
            theorem_axioms={
                "PhysicsAudit.factorization": ["propext", "Classical.choice"]
            }
        )
        ev = collect_lean_evidence(self.config(project), runner=runner)
        self.assertEqual(ev["status"], "PASS")
        self.assertEqual(
            ev["metadata"]["git"]["commit"],
            "0123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(
            ev["metadata"]["audit"]["theorems"][0]["axioms"],
            ["propext", "Classical.choice"],
        )
        self.assertIn("lean-toolchain", ev["metadata"]["toolchain"]["file_sha256"])

    def test_dirty_tree_fails_by_default(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        ev = collect_lean_evidence(self.config(project), runner=FakeRunner(dirty=True))
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("dirty" in x for x in ev["metadata"]["failures"]))

    def test_dirty_tree_can_be_collected_but_is_partial(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        ev = collect_lean_evidence(
            self.config(project, allow_dirty=True),
            runner=FakeRunner(dirty=True),
        )
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(ev["metadata"]["warnings"])

    def test_allowlist_rejects_unexpected_axiom(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        runner = FakeRunner(
            theorem_axioms={
                "PhysicsAudit.factorization": ["propext", "PhysicsAudit.localAxiom"]
            }
        )
        ev = collect_lean_evidence(
            self.config(project, allow_axioms=("propext",)),
            runner=runner,
        )
        self.assertEqual(ev["status"], "FAIL")
        row = ev["metadata"]["audit"]["theorems"][0]
        self.assertEqual(row["unexpected_axioms"], ["PhysicsAudit.localAxiom"])

    def test_sorryax_is_forbidden_without_allowlist(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        runner = FakeRunner(
            theorem_axioms={"PhysicsAudit.factorization": ["sorryAx"]}
        )
        ev = collect_lean_evidence(self.config(project), runner=runner)
        self.assertEqual(ev["status"], "FAIL")
        self.assertEqual(
            ev["metadata"]["audit"]["theorems"][0]["forbidden_axioms_found"],
            ["sorryAx"],
        )

    def test_build_failure_is_evidence_failure(self):
        td, project = self.make_project()
        self.addCleanup(td.cleanup)
        runner = FakeRunner(build_returncode=1)
        ev = collect_lean_evidence(self.config(project), runner=runner)
        self.assertEqual(ev["status"], "FAIL")
        self.assertEqual(ev["metadata"]["build"]["returncode"], 1)
        audit_commands = [
            c for c in runner.commands
            if c[:3] == ("lake", "env", "lean") and c[-1] != "--version"
        ]
        self.assertEqual(audit_commands, [])


if __name__ == "__main__":
    unittest.main()
