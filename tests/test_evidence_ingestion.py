import json
import tempfile
import unittest
from pathlib import Path

from theorygate.evaluate import evaluate_document
from theorygate.io import (
    DocumentError,
    load_evidence_patterns,
    merge_evidence,
    parse_document,
    parse_evidence_payload,
)


class EvidenceIngestionTests(unittest.TestCase):
    def base_doc(self, *, inline_evidence=None):
        return parse_document({
            "model": {"id": "physics-model"},
            "obligations": [
                {"id": "FORMAL_IDENTITY", "kind": "formal"},
                {"id": "REGULATOR_STABILITY", "kind": "robustness"},
            ],
            "evidence": inline_evidence or [],
            "claims": [
                {
                    "id": "FORMAL_CLAIM",
                    "rank": 10,
                    "requires": ["FORMAL_IDENTITY"],
                }
            ],
        })

    def test_single_adapter_record_ingests_and_promotes_claim(self):
        ev = parse_evidence_payload({
            "id": "lean-proof",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
            "metadata": {"git": {"commit": "abc"}},
        }, source="artifacts/lean.json")
        doc = merge_evidence(self.base_doc(), ev)
        report = evaluate_document(doc)
        self.assertTrue(report["claims"]["FORMAL_CLAIM"]["supported"])
        self.assertEqual(report["strongest_supported_claim"], "FORMAL_CLAIM")
        self.assertEqual(
            doc.evidence[0].metadata["theorygate_ingested_from"],
            "artifacts/lean.json",
        )

    def test_bundle_and_list_shapes_are_supported(self):
        one = {
            "id": "e1",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
        }
        two = {
            "id": "e2",
            "obligation": "REGULATOR_STABILITY",
            "status": "PARTIAL",
            "engine": "scan",
        }
        self.assertEqual(len(parse_evidence_payload([one, two], source="x.json")), 2)
        self.assertEqual(
            len(parse_evidence_payload({"evidence": [one, two]}, source="bundle.json")),
            2,
        )
        self.assertEqual(
            len(parse_evidence_payload({"evidence": one}, source="bundle.json")),
            1,
        )

    def test_glob_loading_and_overlapping_patterns_do_not_double_load_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.json").write_text(json.dumps({
                "id": "e1",
                "obligation": "FORMAL_IDENTITY",
                "status": "PASS",
                "engine": "lean",
            }))
            (root / "b.yaml").write_text(
                "evidence:\n"
                "  - id: e2\n"
                "    obligation: REGULATOR_STABILITY\n"
                "    status: PARTIAL\n"
                "    engine: scan\n"
            )
            evidence = load_evidence_patterns([
                str(root / "*.*"),
                str(root / "a.json"),
            ])
            self.assertEqual([e.id for e in evidence], ["e1", "e2"])

    def test_unmatched_pattern_is_error(self):
        with self.assertRaises(DocumentError):
            load_evidence_patterns(["definitely-not-a-real-evidence-file-*.json"])

    def test_duplicate_id_is_rejected_by_default(self):
        doc = self.base_doc(inline_evidence=[{
            "id": "lean-proof",
            "obligation": "FORMAL_IDENTITY",
            "status": "FAIL",
            "engine": "old",
        }])
        external = parse_evidence_payload({
            "id": "lean-proof",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
        }, source="new.json")
        with self.assertRaises(DocumentError):
            merge_evidence(doc, external)

    def test_replace_evidence_is_explicit_and_changes_verdict(self):
        doc = self.base_doc(inline_evidence=[{
            "id": "lean-proof",
            "obligation": "FORMAL_IDENTITY",
            "status": "FAIL",
            "engine": "old",
        }])
        external = parse_evidence_payload({
            "id": "lean-proof",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
        }, source="new.json")
        merged = merge_evidence(doc, external, replace_existing=True)
        report = evaluate_document(merged)
        self.assertTrue(report["claims"]["FORMAL_CLAIM"]["supported"])
        self.assertEqual(merged.evidence[0].engine, "lean")
        self.assertEqual(
            merged.evidence[0].metadata["theorygate_ingested_from"],
            "new.json",
        )

    def test_unknown_obligation_in_external_evidence_is_rejected(self):
        external = parse_evidence_payload({
            "id": "e",
            "obligation": "NOT_IN_MODEL",
            "status": "PASS",
            "engine": "lean",
        }, source="bad.json")
        with self.assertRaises(DocumentError):
            merge_evidence(self.base_doc(), external)

    def test_duplicate_between_two_external_files_is_rejected(self):
        e1 = parse_evidence_payload({
            "id": "same",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
        }, source="a.json")
        e2 = parse_evidence_payload({
            "id": "same",
            "obligation": "FORMAL_IDENTITY",
            "status": "PASS",
            "engine": "lean",
        }, source="b.json")
        with self.assertRaises(DocumentError):
            merge_evidence(self.base_doc(), e1 + e2)


if __name__ == "__main__":
    unittest.main()
