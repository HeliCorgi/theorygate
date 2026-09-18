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

    def collect(self, raw):
        td, path = self.write_spec(raw)
        self.addCleanup(td.cleanup)
        return collect_robustness_evidence(
            spec_path=path,
            evidence_id="scan",
            obligation="ROBUSTNESS",
        )

    def test_clock_reference_scan_passes_with_preregistered_threshold(self):
        ev = self.collect({
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
        self.assertEqual(ev["status"], "PASS")
        self.assertLess(ev["metadata"]["max_symmetric_relative_difference"], 0.05)

    def test_threshold_violation_fails(self):
        ev = self.collect({
            "kind": "ordering",
            "comparison": "pairwise",
            "thresholds": {"max_relative": 0.02},
            "cases": [
                {"label": "ordering-A", "value": 1.0},
                {"label": "ordering-B", "value": 1.1}
            ]
        })
        self.assertEqual(ev["status"], "FAIL")

    def test_no_threshold_is_partial_not_pass(self):
        ev = self.collect({
            "kind": "boundary",
            "comparison": "reference",
            "cases": [
                {"label": "box-1", "value": [1.0, 2.0]},
                {"label": "box-2", "value": [1.001, 2.001]}
            ]
        })
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(ev["metadata"]["diagnostic_only"])

    def test_regulator_increasing_successive_drift_fails(self):
        ev = self.collect({
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
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("increases" in x for x in ev["metadata"]["failures"]))

    def test_too_few_cases_is_partial(self):
        ev = self.collect({
            "kind": "clock",
            "thresholds": {"max_relative": 0.05},
            "minimum_cases": 3,
            "cases": [
                {"label": "a", "value": 1.0},
                {"label": "b", "value": 1.0}
            ]
        })
        self.assertEqual(ev["status"], "PARTIAL")

    def test_preregistered_fixed_plateau_passes(self):
        ev = self.collect({
            "kind": "regulator",
            "comparison": "plateau",
            "plateau_selection": "fixed",
            "plateau_window": {"min_setting": 0.04, "max_setting": 0.08},
            "minimum_plateau_cases": 3,
            "minimum_setting_span": 0.02,
            "thresholds": {"max_relative_within_plateau": 0.05},
            "cases": [
                {"label": ".02", "setting": 0.02, "value": 1.4},
                {"label": ".04", "setting": 0.04, "value": 1.000},
                {"label": ".06", "setting": 0.06, "value": 1.010},
                {"label": ".08", "setting": 0.08, "value": 0.995},
                {"label": ".10", "setting": 0.10, "value": 1.3}
            ]
        })
        self.assertEqual(ev["status"], "PASS")
        self.assertEqual(ev["metadata"]["plateau_selection"], "fixed")
        self.assertEqual(ev["metadata"]["selected_plateau"]["case_count"], 3)

    def test_preregistered_criterion_can_find_broad_plateau(self):
        ev = self.collect({
            "kind": "regulator",
            "comparison": "plateau",
            "plateau_selection": "criterion",
            "minimum_plateau_cases": 3,
            "minimum_setting_span": 0.03,
            "thresholds": {"max_relative_within_plateau": 0.04},
            "cases": [
                {"label": "a", "setting": 0.00, "value": 1.4},
                {"label": "b", "setting": 0.02, "value": 1.00},
                {"label": "c", "setting": 0.04, "value": 1.01},
                {"label": "d", "setting": 0.06, "value": 0.99},
                {"label": "e", "setting": 0.08, "value": 1.3}
            ]
        })
        self.assertEqual(ev["status"], "PASS")
        self.assertTrue(ev["metadata"]["stable_windows"])

    def test_exploratory_plateau_never_promotes_to_pass(self):
        ev = self.collect({
            "kind": "regulator",
            "comparison": "plateau",
            "plateau_selection": "exploratory",
            "minimum_plateau_cases": 3,
            "minimum_setting_span": 0.03,
            "thresholds": {"max_relative_within_plateau": 0.04},
            "cases": [
                {"label": "a", "setting": 0.00, "value": 1.4},
                {"label": "b", "setting": 0.02, "value": 1.00},
                {"label": "c", "setting": 0.04, "value": 1.01},
                {"label": "d", "setting": 0.06, "value": 0.99},
                {"label": "e", "setting": 0.08, "value": 1.3}
            ]
        })
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(ev["metadata"]["stable_windows"])
        self.assertTrue(any("exploratory" in x for x in ev["metadata"]["warnings"]))

    def test_astra_cap_narrow_minimum_fails_broad_plateau_criterion(self):
        ev = self.collect({
            "kind": "regulator",
            "observable": "max_abs_Doff",
            "comparison": "plateau",
            "plateau_selection": "criterion",
            "minimum_plateau_cases": 3,
            "minimum_setting_span": 0.02,
            "thresholds": {"max_relative_within_plateau": 0.05},
            "cases": [
                {"label": ".025", "setting": 0.025, "value": 0.11048},
                {"label": ".040", "setting": 0.040, "value": 0.05358},
                {"label": ".050", "setting": 0.050, "value": 0.03210},
                {"label": ".060", "setting": 0.060, "value": 0.01666},
                {"label": ".075", "setting": 0.075, "value": 0.00733},
                {"label": ".085", "setting": 0.085, "value": 0.01361},
                {"label": ".100", "setting": 0.100, "value": 0.02323}
            ]
        })
        self.assertEqual(ev["status"], "FAIL")
        self.assertTrue(any("no contiguous broad plateau" in x for x in ev["metadata"]["failures"]))

    def test_plateau_without_variation_threshold_is_partial(self):
        ev = self.collect({
            "kind": "regulator",
            "comparison": "plateau",
            "plateau_selection": "criterion",
            "minimum_plateau_cases": 3,
            "cases": [
                {"label": "a", "setting": 0.0, "value": 1.0},
                {"label": "b", "setting": 0.1, "value": 1.0},
                {"label": "c", "setting": 0.2, "value": 1.0}
            ]
        })
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(ev["metadata"]["diagnostic_only"])

    def test_fixed_plateau_with_insufficient_sample_coverage_is_partial(self):
        ev = self.collect({
            "kind": "regulator",
            "comparison": "plateau",
            "plateau_selection": "fixed",
            "plateau_window": {"min_setting": 0.04, "max_setting": 0.08},
            "minimum_plateau_cases": 3,
            "minimum_setting_span": 0.03,
            "thresholds": {"max_relative_within_plateau": 0.05},
            "cases": [
                {"label": ".04", "setting": 0.04, "value": 1.0},
                {"label": ".06", "setting": 0.06, "value": 1.0}
            ]
        })
        self.assertEqual(ev["status"], "PARTIAL")
        self.assertTrue(any("minimum_plateau_cases" in x for x in ev["metadata"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
