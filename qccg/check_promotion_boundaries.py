#!/usr/bin/env python3
"""Stable promotion-boundary checks for the QCCG TheoryGate field trial.

The checker intentionally distinguishes:
- scoped toy/calibration obligations that must PASS;
- unresolved/falsifiable physical promotion gates that must NOT PASS;
- strong physical claims (rank >= 50) that must remain unsupported.

OPEN vs BLOCKED is not hard-coded for terminal physical gates because adding a
new prerequisite legitimately changes OPEN -> BLOCKED without changing the
scientific promotion boundary.  FAIL is also a valid negative scientific
outcome and therefore is not converted into a CI infrastructure failure for a
terminal physical gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


MUST_PASS = {
    "FINITE_WEYL_ALGEBRA",
    "WEYL_QUADRATIC_LIMIT",
    "D4_RECIPROCITY_ALGEBRA",
    "TT_QUADRATIC_SPECTRUM",
    "FINITE_SIZE_GAP_SCALING",
    "DEFECT_GAP_STABILITY",
    "FULL_MICROSCOPIC_DERIVATION",
    "CELLULATION_LIQUID_ZERO_MODE",
    "CELLULATION_CONNECTIVITY_CONTROL",
    "MANIFOLD_DIAGNOSTIC_CALIBRATED",
    "MANIFOLD_DIMENSION_CONTROLS",
    "PACHNER_4D_MANIFOLD_TOPOLOGY_CONTROL",
    "UNWEIGHTED_PACHNER_DIMENSION_FAILURE_DETECTED",
    "PACHNER_MOVESET_REPAIR_INSUFFICIENT",
    "REGGE_WEIGHTED_PACHNER_SCAN_EXECUTED",
    "SIMPLE_REGGE_WEIGHT_REPAIR_INSUFFICIENT",
    "CAUSAL_FOLIATED_4D_ARCHITECTURE",
    "CAUSAL_FOLIATION_NEGATIVE_CONTROL",
    "CAUSAL_LOCAL_MOVESET_TOY",
    "CAUSAL_MOVE_HERMITIAN_TOY",
    "CAUSAL_MOVE_NEGATIVE_CONTROL",
    "CAUSAL_MOVE_ENSEMBLE_SCAN_EXECUTED",
    "CAUSAL_FIXED_VERTEX_MOVESET_INSUFFICIENT",
    "CAUSAL_COLUMN_MOVESET_TOY",
    "CAUSAL_COLUMN_ENSEMBLE_SCAN_EXECUTED",
    "BARE_SPATIAL_ISOTROPY",
    "LATTICE_LV_IRRELEVANT",
    "LINEARIZED_CONSTRAINT_ALGEBRA",
    "TT_PROJECTOR_RANK2",
    "HDA_NONABELIAN_TARGET",
    "COMMUTING_PROJECTOR_HDA_REJECTED",
    "STRUCTURE_FUNCTION_CLOSURE_TOY",
    "CONSTRAINT_KERNEL_GAP_TOY",
    "STRUCTURE_FUNCTION_NEGATIVE_CONTROL",
    "FINITE_GLOBAL_CCR_NO_GO",
    "LOW_ENERGY_STRUCTURE_FUNCTION_CONVERGENCE",
    "STRUCTURE_FUNCTION_PATCH_CONTROL",
    "ONE_D_HDA_STRUCTURE_FUNCTION_CODE_MATCH",
    "ONE_D_HDA_ALIASING_NEGATIVE_CONTROL",
    "FINITE_PARENT_UNITARITY",
    "QUADRATIC_SCALING_ISOMETRY",
    "INTERACTING_CODE_INTERTWINER_TOY",
    "SCALING_LEAKAGE_NEGATIVE_CONTROL",
    "GRAPH_CHANGE_INTERTWINER_TOY",
    "GRAPH_CHANGE_LEAKAGE_NEGATIVE_CONTROL",
    "REFINEMENT_PATH_COHERENCE_TOY",
    "REFINEMENT_COHERENCE_NEGATIVE_CONTROL",
    "CUBIC_VERTEX_OBSTRUCTION_DETECTED",
    "GENERIC_CUBIC_INTERACTION_REPAIR",
    "CUBIC_VACUUM_STABILITY_CONTROL",
    "NONDERIVATIVE_CUBIC_MISMATCH_DETECTED",
    "DERIVATIVE_CUBIC_REPAIR",
    "GR_CUBIC_WARD_KINEMATIC_CONTROL",
    "GR_CUBIC_GAUGE_REPLACEMENT_CONTROL",
    "QCCG_TENSOR_CUBIC_VERTEX_CONSTRUCTED",
    "QCCG_CUBIC_SELECTED_WARD_MATCH",
    "QCCG_CUBIC_MULTI_KINEMATICS_STRESS",
    "SOFT_GRAVITON_UNIVERSALITY_TARGET",
    "SOFT_NONUNIVERSAL_COUPLING_REJECTED",
    "RG_BRIDGE_OBSERVABLES_EXTRACTED",
    "IR_TWO_POINT_MATCH_INSUFFICIENT",
    "EXACT_FINITE_RG_BLOCKING_TOY",
    "SINGLE_COUPLING_RG_TRUNCATION_REJECTED",
    "FULL_FINITE_HARMONIC_RG_CLOSURE_TOY",
    "TRIVIAL_RG_FLOW_NEGATIVE_CONTROL",
    "FESHBACH_COARSE_GRAINING_TOY",
    "COARSE_OPERATOR_PROLIFERATION_DETECTED",
    "FINITE_EFFECTIVE_BASIS_CLOSURE_TOY",
    "ENERGY_DEPENDENT_EFFECTIVE_KERNEL_DETECTED",
    "CELLULATION_FESHBACH_RG_TOY",
    "CELLULATION_RESTRICTED_RG_BASIS_REJECTED",
    "CELLULATION_FULL_OPERATOR_BASIS_CLOSURE_TOY",
    "CELLULATION_ENERGY_DEPENDENT_KERNEL",
}

MUST_NOT_PASS = {
    "QCCG_CAUSAL_MOVE_DYNAMICS",
    "QCCG_CAUSAL_CRITICAL_CELLULATION_DYNAMICS",
    "CAUSAL_4D_SCALING_STABILITY",
    "QCCG_TIME_LOCAL_CAUSAL_DYNAMICS",
    "QCCG_WEIGHTED_CRITICAL_CELLULATION_ENSEMBLE",
    "QCCG_CELLULATION_GEOMETRY_MEASURED",
    "MANIFOLD_LIKENESS_SCALING",
    "CONTINUUM_MANIFOLD_PHASE",
    "MARGINAL_LV_STABILITY",
    "LORENTZ_UNIVERSALITY",
    "QCCG_CELLULATION_REFINEMENT_COHERENCE",
    "QCCG_GRAPH_CHANGING_SCALING_MAP",
    "INTERACTING_PHYSICAL_SCALING_UNITARITY",
    "PHYSICAL_UNITARITY_SCALING_LIMIT",
    "QCCG_FULL_CUBIC_WARD_MATCH",
    "GR_CUBIC_VERTEX_MATCH",
    "GR_HDA_STRUCTURE_FUNCTION_MATCH",
    "NONLINEAR_CONSTRAINT_CLOSURE",
    "CONTINUUM_DIFFEO_BRST",
    "QCCG_GRAPH_CHANGING_EFFECTIVE_KERNEL",
    "QCCG_CELLULATION_NONPERTURBATIVE_RG",
    "QCCG_NONPERTURBATIVE_RG_FLOW",
    "ESSENTIAL_CRITICAL_EXPONENT_MATCH",
    "AS_FIXED_POINT_MATCH",
    "PHYSICAL_MASSLESS_SPIN2_CONTINUUM",
    "UNIVERSAL_COUPLING_PHYSICAL",
    "GR_IR_EFFECTIVE_ACTION",
    "STRONG_GRAVITY_CTP",
}

STRONG_CLAIMS = {
    "QCCG_EMERGENT_MASSLESS_SPIN2",
    "QCCG_RFQG_UNIVERSALITY",
    "QCCG_GR_IR",
    "QCCG_STRONG_GRAVITY",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    obligations = report["obligations"]
    claims = report["claims"]
    failures = []

    for oid in sorted(MUST_PASS):
        status = obligations.get(oid, {}).get("status")
        if status != "PASS":
            failures.append(f"{oid}: expected PASS, got {status}")

    for oid in sorted(MUST_NOT_PASS):
        status = obligations.get(oid, {}).get("status")
        if status == "PASS":
            failures.append(f"{oid}: physical promotion gate unexpectedly PASS")
        if status is None:
            failures.append(f"{oid}: missing from report")

    for cid in sorted(STRONG_CLAIMS):
        row = claims.get(cid)
        if row is None:
            failures.append(f"{cid}: missing claim")
        elif row["supported"]:
            failures.append(f"{cid}: strong physical claim unexpectedly SUPPORTED")

    strongest_id = report.get("strongest_supported_claim")
    if strongest_id is not None:
        rank = claims[strongest_id]["rank"]
        if rank >= 50:
            failures.append(
                f"strongest_supported_claim={strongest_id} has rank {rank} >= 50"
            )

    summary = {
        "strongest_supported_claim": strongest_id,
        "must_pass_count": len(MUST_PASS),
        "must_not_pass_count": len(MUST_NOT_PASS),
        "strong_claims": sorted(STRONG_CLAIMS),
        "failures": failures,
        "terminal_statuses": {
            oid: obligations.get(oid, {}).get("status")
            for oid in sorted(MUST_NOT_PASS)
        },
    }

    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failures:
        raise SystemExit("promotion boundary failure:\n- " + "\n- ".join(failures))


if __name__ == "__main__":
    main()
