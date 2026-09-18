from __future__ import annotations

from copy import deepcopy


# These are conservative starter policies, not statements of universal
# consensus. They make hidden physical interpretation obligations explicit and
# are intended to be edited for the actual model.
_TEMPLATES = {
    "HISTORY_PROBABILITY": {
        "description": (
            "Promote model-internal branch weights to ordinary additive history "
            "probabilities only after class-operator, inner-product, decoherence "
            "and robustness obligations are discharged."
        ),
        "obligations": [
            {"id": "CLASS_OPERATOR_DEFINED", "kind": "formal"},
            {"id": "PROJECTOR_FAMILY_DEFINED", "kind": "formal"},
            {"id": "PHYSICAL_INNER_PRODUCT", "kind": "physical"},
            {"id": "DECOHERENCE", "kind": "numerical"},
            {"id": "REGULATOR_STABILITY", "kind": "robustness"},
            {"id": "BOUNDARY_ROBUSTNESS", "kind": "robustness"},
        ],
        "claim": {
            "id": "HISTORY_PROBABILITY",
            "rank": 50,
            "statement": (
                "The declared history weights may be interpreted as ordinary "
                "additive probabilities at the audited scope."
            ),
            "requires": [
                "CLASS_OPERATOR_DEFINED",
                "PROJECTOR_FAMILY_DEFINED",
                "PHYSICAL_INNER_PRODUCT",
                "DECOHERENCE",
                "REGULATOR_STABILITY",
                "BOUNDARY_ROBUSTNESS",
            ],
        },
    },
    "PHYSICAL_OBSERVABLE": {
        "description": (
            "Promote a model quantity to a physical observable only after its "
            "operator/domain, physical inner product, correspondence and major "
            "quantization/regulator sensitivities are audited."
        ),
        "obligations": [
            {"id": "OBSERVABLE_OPERATOR_DEFINED", "kind": "formal"},
            {"id": "OBSERVABLE_DOMAIN_DEFINED", "kind": "formal"},
            {"id": "PHYSICAL_INNER_PRODUCT", "kind": "physical"},
            {"id": "MEASUREMENT_OR_SELF_ADJOINTNESS", "kind": "formal"},
            {"id": "SEMICLASSICAL_CORRESPONDENCE", "kind": "physics"},
            {"id": "CLOCK_ROBUSTNESS", "kind": "robustness"},
            {"id": "ORDERING_ROBUSTNESS", "kind": "robustness"},
            {"id": "REGULATOR_STABILITY", "kind": "robustness"},
            {"id": "BOUNDARY_ROBUSTNESS", "kind": "robustness"},
        ],
        "claim": {
            "id": "PHYSICAL_OBSERVABLE",
            "rank": 60,
            "statement": (
                "The audited quantity is supported as a physical observable "
                "within the explicitly stated model scope."
            ),
            "requires": [
                "OBSERVABLE_OPERATOR_DEFINED",
                "OBSERVABLE_DOMAIN_DEFINED",
                "PHYSICAL_INNER_PRODUCT",
                "MEASUREMENT_OR_SELF_ADJOINTNESS",
                "SEMICLASSICAL_CORRESPONDENCE",
                "CLOCK_ROBUSTNESS",
                "ORDERING_ROBUSTNESS",
                "REGULATOR_STABILITY",
                "BOUNDARY_ROBUSTNESS",
            ],
        },
    },
    "TIMELESS_CLASS_OPERATOR": {
        "description": (
            "Audit promotion from finite-clock sequential projections to a "
            "constraint-compatible timeless class operator."
        ),
        "obligations": [
            {"id": "CONSTRAINT_OPERATOR_DEFINED", "kind": "formal"},
            {"id": "CLASS_OPERATOR_DEFINED", "kind": "formal"},
            {"id": "CLASS_OPERATOR_CONSTRAINT_COMPATIBLE", "kind": "formal"},
            {"id": "PHYSICAL_INNER_PRODUCT", "kind": "physical"},
            {"id": "REGULATOR_STABILITY", "kind": "robustness"},
            {"id": "BOUNDARY_ROBUSTNESS", "kind": "robustness"},
        ],
        "claim": {
            "id": "TIMELESS_PHYSICAL_CLASS_OPERATOR",
            "rank": 70,
            "statement": (
                "A constraint-compatible timeless physical class operator is "
                "supported at the audited scope."
            ),
            "requires": [
                "CONSTRAINT_OPERATOR_DEFINED",
                "CLASS_OPERATOR_DEFINED",
                "CLASS_OPERATOR_CONSTRAINT_COMPATIBLE",
                "PHYSICAL_INNER_PRODUCT",
                "REGULATOR_STABILITY",
                "BOUNDARY_ROBUSTNESS",
            ],
        },
    },
    "SINGULARITY_RESOLUTION": {
        "description": (
            "A deliberately strict starter template. 'Singularity resolution' "
            "must define its criterion and connect the relevant physical "
            "observable/domain to that criterion while surviving major model "
            "and regulator choices."
        ),
        "obligations": [
            {"id": "SINGULARITY_CRITERION_DEFINED", "kind": "physics"},
            {"id": "PHYSICAL_OBSERVABLE", "kind": "physics"},
            {"id": "OBSERVABLE_DOMAIN_DEFINED", "kind": "formal"},
            {"id": "PHYSICAL_INNER_PRODUCT", "kind": "physical"},
            {"id": "CRITERION_SATISFIED", "kind": "physics"},
            {"id": "SEMICLASSICAL_CORRESPONDENCE", "kind": "physics"},
            {"id": "CLOCK_ROBUSTNESS", "kind": "robustness"},
            {"id": "ORDERING_ROBUSTNESS", "kind": "robustness"},
            {"id": "REGULATOR_STABILITY", "kind": "robustness"},
            {"id": "BOUNDARY_ROBUSTNESS", "kind": "robustness"},
        ],
        "claim": {
            "id": "SINGULARITY_RESOLUTION",
            "rank": 100,
            "statement": (
                "The explicitly defined singularity-resolution criterion is "
                "supported at the audited physical scope."
            ),
            "requires": [
                "SINGULARITY_CRITERION_DEFINED",
                "PHYSICAL_OBSERVABLE",
                "OBSERVABLE_DOMAIN_DEFINED",
                "PHYSICAL_INNER_PRODUCT",
                "CRITERION_SATISFIED",
                "SEMICLASSICAL_CORRESPONDENCE",
                "CLOCK_ROBUSTNESS",
                "ORDERING_ROBUSTNESS",
                "REGULATOR_STABILITY",
                "BOUNDARY_ROBUSTNESS",
            ],
        },
    },
}

TEMPLATE_NAMES = tuple(sorted(_TEMPLATES))


def get_template(name: str) -> dict:
    key = name.upper()
    if key not in _TEMPLATES:
        raise KeyError(f"unknown physical claim template: {name}")
    return deepcopy(_TEMPLATES[key])


def render_template_document(
    name: str,
    *,
    model_id: str,
    title: str | None = None,
) -> dict:
    template = get_template(name)
    obligations = []
    for item in template["obligations"]:
        obligations.append({
            "id": item["id"],
            "title": item["id"].replace("_", " ").title(),
            "kind": item.get("kind", "unspecified"),
            "description": (
                f"Template obligation for {name}. Replace this description with "
                "the model-specific statement and scope before treating it as a gate."
            ),
        })
    claim = deepcopy(template["claim"])
    claim["title"] = claim["id"].replace("_", " ").title()
    return {
        "version": "0.4",
        "model": {
            "id": model_id,
            "title": title or model_id,
            "choices": {},
        },
        "obligations": obligations,
        "evidence": [],
        "claims": [claim],
        "template_metadata": {
            "name": name.upper(),
            "description": template["description"],
            "warning": (
                "Built-in templates are conservative starter policies, not a "
                "substitute for model-specific expert judgment. Edit obligations "
                "to match the actual physical claim."
            ),
        },
    }
