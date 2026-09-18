import json
import tempfile
import unittest
from pathlib import Path

from theorygate.adapters.cas import (
    CommandResult,
    ExternalCASConfig,
    collect_external_cas_evidence,
    collect_sympy_evidence,
)


class FakeCASRunner:
    def __init__(self, *, marker="THEORYGATE:PASS", returncode=0):
        self.marker = marker
        self.returncode = returncode
        self.commands = []

    def __call__(self, command, cwd, timeout):
        cmd = tuple(command)
        self.commands.append(cmd)
        if "--version" in cmd or "-version" in cmd:
            return CommandResult(cmd, 0, "FakeCAS 1.0\n", "")
        return CommandResult(cmd, self.returncode, self.marker + "\n", "")


class CASAdapterTests(unittest.TestCase):
    def write_spec(self, raw):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "spec.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return td, path

    def test_sympy_identity_passes(self):
        td, path = self.write_spec({
            "symbols": {"x": {"real": True}},
            "checks": [
                {
                    "id": "trig",
                    "lhs": "sin(x)**2 + cos(x)**2",
                    "rhs": "1",
                    "method": "trigsimp"
                },
                {
                    "id": "factor",
                    "lhs": "(x + 1)**2",
                    "rhs": "x**2 + 2*x + 1",
                    "method": "expand"
                }
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_sympy_evidence(
            spec_path=path,
            evidence_id="sympy",
            obligation="ALGEBRA",
        )
        self.assertEqual(ev["status"], "PASS")
        self.assertEqual(len(ev["metadata"]["checks"]), 2)
        self.assertTrue(all(row["passed"] for row in ev["metadata"]["checks"]))

    def test_sympy_nonidentity_fails(self):
        td, path = self.write_spec({
            "symbols": {"x": {"real": True}},
            "checks": [{"id": "wrong", "lhs": "x + 1", "rhs": "x"}]
        })
        self.addCleanup(td.cleanup)
        ev = collect_sympy_evidence(
            spec_path=path,
            evidence_id="sympy",
            obligation="ALGEBRA",
        )
        self.assertEqual(ev["status"], "FAIL")
        self.assertFalse(ev["metadata"]["checks"][0]["passed"])

    def test_xact_marker_contract_passes(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "audit.wls"
            script.write_text('Print["THEORYGATE:PASS"]\n', encoding="utf-8")
            runner = FakeCASRunner()
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="xact",
                    script=script,
                    evidence_id="xact",
                    obligation="GR_REDUCTION",
                ),
                runner=runner,
            )
        self.assertEqual(ev["status"], "PASS")
        self.assertEqual(ev["engine"], "xact")
        self.assertTrue(ev["metadata"]["script_sha256"])

    def test_cadabra_missing_marker_fails(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "audit.cdb"
            script.write_text("# synthetic\n", encoding="utf-8")
            runner = FakeCASRunner(marker="ordinary output")
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="cadabra",
                    script=script,
                    evidence_id="cadabra",
                    obligation="TENSOR_IDENTITY",
                ),
                runner=runner,
            )
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("pass marker" in x for x in ev["metadata"]["failures"]))

    def test_explicit_fail_marker_fails_even_with_zero_exit(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "audit.wls"
            script.write_text("(* synthetic *)\n", encoding="utf-8")
            runner = FakeCASRunner(marker="THEORYGATE:FAIL")
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="xact",
                    script=script,
                    evidence_id="xact",
                    obligation="GR_REDUCTION",
                ),
                runner=runner,
            )
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("failure marker" in x for x in ev["metadata"]["failures"]))

    def test_maxima_preset_records_standard_batch_command(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "reduction.mac"
            script.write_text('print("THEORYGATE:PASS")$\n', encoding="utf-8")
            runner = FakeCASRunner()
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="maxima",
                    script=script,
                    evidence_id="maxima",
                    obligation="GR_REDUCTION",
                ),
                runner=runner,
            )
        self.assertEqual(ev["status"], "PASS")
        command = ev["metadata"]["command"]
        self.assertEqual(command[0], "maxima")
        self.assertIn("--quiet", command)
        self.assertIn("--quit-on-error", command)
        self.assertTrue(any(arg.startswith("--batch=") for arg in command))
        self.assertEqual(ev["metadata"]["engine_preset"], "maxima")

    def test_generic_external_cas_supports_custom_argument_vectors(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "audit.in"
            script.write_text("synthetic\n", encoding="utf-8")
            runner = FakeCASRunner()
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="reduce",
                    executable="redcsl",
                    script=script,
                    command_args=("--batch", "{script}"),
                    version_args=("--version",),
                    evidence_id="reduce",
                    obligation="ALGEBRA",
                ),
                runner=runner,
            )
        self.assertEqual(ev["status"], "PASS")
        self.assertEqual(
            ev["metadata"]["command"],
            ["redcsl", "--batch", str(script.resolve())],
        )
        self.assertIsNone(ev["metadata"]["engine_preset"])

    def test_generic_external_cas_requires_executable(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "audit.in"
            script.write_text("synthetic\n", encoding="utf-8")
            ev = collect_external_cas_evidence(
                ExternalCASConfig(
                    engine="unknown-cas",
                    script=script,
                    evidence_id="external",
                    obligation="ALGEBRA",
                ),
                runner=FakeCASRunner(),
            )
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("explicit executable" in x for x in ev["metadata"]["failures"]))


if __name__ == "__main__":
    unittest.main()
