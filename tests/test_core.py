import json
import tempfile
import unittest
from pathlib import Path

from theorygate.evaluate import evaluate_document
from theorygate.io import DocumentError, load_document, parse_document


class TheoryGateTests(unittest.TestCase):
    def test_astra_example_promotes_only_branch_weight(self):
        doc = load_document("examples/astra_blackhole.json")
        report = evaluate_document(doc)
        self.assertEqual(report["strongest_supported_claim"], "MODEL_INTERNAL_BRANCH_WEIGHT")
        self.assertTrue(report["claims"]["MODEL_INTERNAL_BRANCH_WEIGHT"]["supported"])
        self.assertFalse(report["claims"]["HISTORY_PROBABILITY"]["supported"])
        self.assertEqual(report["obligations"]["DECOHERENCE"]["status"], "FAIL")
        self.assertEqual(report["obligations"]["PHYSICAL_INNER_PRODUCT"]["status"], "OPEN")

    def test_model_choice_must_be_explicitly_accepted(self):
        raw = {
            "model": {"id": "m"},
            "obligations": [{"id": "CLOCK"}],
            "evidence": [
                {
                    "id": "e",
                    "obligation": "CLOCK",
                    "status": "MODEL_CHOICE",
                    "engine": "model-spec"
                }
            ],
            "claims": [
                {"id": "STRICT", "requires": ["CLOCK"]},
                {
                    "id": "MODEL_INTERNAL",
                    "rank": 1,
                    "requires": [{"id": "CLOCK", "accept": ["PASS", "MODEL_CHOICE"]}]
                }
            ]
        }
        report = evaluate_document(parse_document(raw))
        self.assertFalse(report["claims"]["STRICT"]["supported"])
        self.assertTrue(report["claims"]["MODEL_INTERNAL"]["supported"])
        self.assertEqual(
            report["claims"]["MODEL_INTERNAL"]["caveats"],
            ["CLOCK=MODEL_CHOICE"]
        )

    def test_failed_dependency_blocks_downstream_obligation(self):
        raw = {
            "model": {"id": "m"},
            "obligations": [
                {"id": "A"},
                {"id": "B", "depends_on": ["A"]}
            ],
            "evidence": [
                {"id": "ea", "obligation": "A", "status": "FAIL", "engine": "test"},
                {"id": "eb", "obligation": "B", "status": "PASS", "engine": "test"}
            ],
            "claims": []
        }
        report = evaluate_document(parse_document(raw))
        self.assertEqual(report["obligations"]["A"]["status"], "FAIL")
        self.assertEqual(report["obligations"]["B"]["status"], "BLOCKED")

    def test_cycle_rejected(self):
        raw = {
            "model": {"id": "m"},
            "obligations": [
                {"id": "A", "depends_on": ["B"]},
                {"id": "B", "depends_on": ["A"]}
            ],
            "evidence": [],
            "claims": []
        }
        with self.assertRaises(DocumentError):
            parse_document(raw)

    def test_unknown_reference_rejected(self):
        raw = {
            "model": {"id": "m"},
            "obligations": [{"id": "A"}],
            "evidence": [],
            "claims": [{"id": "C", "requires": ["NOPE"]}]
        }
        with self.assertRaises(DocumentError):
            parse_document(raw)


if __name__ == "__main__":
    unittest.main()
