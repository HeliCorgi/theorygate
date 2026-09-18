import json
import tempfile
import unittest
from pathlib import Path

from theorygate.adapters.robustness import collect_robustness_evidence


class RobustnessAdapterTests(unittest.TestCase):
    def write_spec(self, raw):
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "scan.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        return td, path

    def test_clock_reference_scan_passes_with_preregistered_threshold(self):
        td, path = self.write_spec({
            "kind": "clock",
            "observable": "branch_weight",
            "comparison": "reference",
            "reference": "clock-A",
            "thresholds": {"max_relative": 0.05},
            "minimum_cases": 3,
            "cases": [
                {"label": "clock-A", "value": 0.300},
                {"label": "clock-B", "value": 0.304},
                {"label": "clock-C", "value": 0.297}
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_robustness_evidence(
            spec_path=path,
            evidence_id="clock-scan",
            obligation="CLOCK_ROBUSTNESS",
        )
        self.assertEqual(ev["status"], "PASS")
        self.assertLess(ev["metadata"]["max_symmetric_relative_difference"], 0.05)

    def test_threshold_violation_fails(self):
        td, path = self.write_spec({
            "kind": "ordering",
            "comparison": "pairwise",
            "thresholds": {"max_relative": 0.02},
            "cases": [
                {"label": "ordering-A", "value": 1.0},
                {"label": "ordering-B", "value": 1.1}
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_robustness_evidence(
            spec_path=path,
            evidence_id="ordering",
            obligation="ORDERING_ROBUSTNESS",
        )
        self.assertEqual(ev["status"], "FAIL")

    def test_no_threshold_is_partial_not_pass(self):
        td, path = self.write_spec({
            "kind": "boundary",
            "comparison": "reference",
            "cases": [
                {"label": "box-1", "value": [1.0, 2.0]},
                {"label": "box-2", "value": [1.001, 2.001]}
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_robustness_evidence(
            spec_path=path,
            evidence_id="boundary",
            obligation="BOUNDARY_ROBUSTNESS",
        )
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(ev["metadata"]["diagnostic_only"])

    def test_regulator_increasing_successive_drift_fails(self):
        td, path = self.write_spec({
            "kind": "regulator",
            "observable": "T_action",
            "comparison": "successive",
            "thresholds": {"max_relative": 1.0},
            "require_nonincreasing_successive_drift": True,
            "cases": [
                {"label": "eta=.1", "setting": 0.1, "value": 1.00},
                {"label": "eta=.05", "setting": 0.05, "value": 1.01},
                {"label": "eta=.025", "setting": 0.025, "value": 1.05}
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_robustness_evidence(
            spec_path=path,
            evidence_id="eta",
            obligation="REGULATOR_STABILITY",
        )
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("increases" in x for x in ev["metadata"]["failures"]))

    def test_too_few_cases_is_partial(self):
        td, path = self.write_spec({
            "kind": "clock",
            "thresholds": {"max_relative": 0.05},
            "minimum_cases": 3,
            "cases": [
                {"label": "a", "value": 1.0},
                {"label": "b", "value": 1.0}
            ]
        })
        self.addCleanup(td.cleanup)
        ev = collect_robustness_evidence(
            spec_path=path,
            evidence_id="few",
            obligation="CLOCK_ROBUSTNESS",
        )
        self.assertEqual(ev["status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
