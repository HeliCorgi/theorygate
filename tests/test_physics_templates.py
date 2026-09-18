import unittest

from theorygate.io import parse_document
from theorygate.templates.physics import TEMPLATE_NAMES, get_template, render_template_document


class PhysicsTemplateTests(unittest.TestCase):
    def test_required_templates_exist(self):
        for name in (
            "HISTORY_PROBABILITY",
            "PHYSICAL_OBSERVABLE",
            "TIMELESS_CLASS_OPERATOR",
            "SINGULARITY_RESOLUTION",
        ):
            self.assertIn(name, TEMPLATE_NAMES)

    def test_history_probability_template_contains_decoherence(self):
        t = get_template("HISTORY_PROBABILITY")
        ids = {x["id"] for x in t["obligations"]}
        self.assertIn("DECOHERENCE", ids)
        self.assertIn("PHYSICAL_INNER_PRODUCT", ids)

    def test_singularity_template_requires_robustness_axes(self):
        t = get_template("SINGULARITY_RESOLUTION")
        req = set(t["claim"]["requires"])
        self.assertIn("CLOCK_ROBUSTNESS", req)
        self.assertIn("ORDERING_ROBUSTNESS", req)
        self.assertIn("BOUNDARY_ROBUSTNESS", req)
        self.assertIn("REGULATOR_STABILITY", req)

    def test_rendered_template_is_valid_theorygate_document(self):
        raw = render_template_document(
            "PHYSICAL_OBSERVABLE",
            model_id="toy-quantum-gravity",
            title="Toy quantum gravity audit",
        )
        doc = parse_document(raw)
        self.assertEqual(doc.model.id, "toy-quantum-gravity")
        self.assertEqual(doc.claims[0].id, "PHYSICAL_OBSERVABLE")


if __name__ == "__main__":
    unittest.main()
