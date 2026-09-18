from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import yaml


VALID_KINDS = {"regulator", "clock", "ordering", "boundary"}


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


def _vector(value: Any) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, list) and value and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in value
    ):
        return [float(x) for x in value]
    raise ValueError("case value must be a number or non-empty numeric list")


def _distance(a: list[float], b: list[float]) -> tuple[float, float]:
    if len(a) != len(b):
        raise ValueError("all robustness values must have the same dimension")
    abs_diff = max(abs(x - y) for x, y in zip(a, b))
    rels = []
    for x, y in zip(a, b):
        den = abs(x) + abs(y)
        rels.append(0.0 if den == 0 else 2.0 * abs(x - y) / den)
    return abs_diff, max(rels, default=0.0)


def collect_robustness_evidence(
    *,
    spec_path: str | Path,
    evidence_id: str,
    obligation: str,
    artifact: str | None = None,
) -> dict:
    """Evaluate a preregistered robustness scan.

    No tolerance is invented by TheoryGate. If the spec contains no absolute or
    relative threshold, diagnostics are produced as PARTIAL rather than PASS.
    """
    path = Path(spec_path).expanduser().resolve()
    failures: list[str] = []
    warnings: list[str] = []
    try:
        raw = _load(path)
    except Exception as exc:
        raw = {}
        failures.append(f"could not load robustness spec: {exc}")

    if not isinstance(raw, dict):
        failures.append("robustness spec root must be an object")
        raw = {}

    kind = str(raw.get("kind", "")).lower()
    if kind not in VALID_KINDS:
        failures.append(
            "kind must be one of regulator, clock, ordering, boundary"
        )

    cases_raw = raw.get("cases", [])
    if not isinstance(cases_raw, list):
        failures.append("cases must be a list")
        cases_raw = []

    cases = []
    for i, item in enumerate(cases_raw):
        if not isinstance(item, dict) or "label" not in item or "value" not in item:
            failures.append(f"case {i}: requires label and value")
            continue
        try:
            vec = _vector(item["value"])
        except ValueError as exc:
            failures.append(f"case {i}: {exc}")
            continue
        cases.append({
            "label": str(item["label"]),
            "setting": item.get("setting"),
            "value": vec,
        })

    thresholds = raw.get("thresholds", {})
    if thresholds is None:
        thresholds = {}
    if not isinstance(thresholds, dict):
        failures.append("thresholds must be an object")
        thresholds = {}
    max_abs_allowed = thresholds.get("max_absolute")
    max_rel_allowed = thresholds.get("max_relative")
    if max_abs_allowed is not None:
        max_abs_allowed = float(max_abs_allowed)
        if max_abs_allowed < 0:
            failures.append("max_absolute must be non-negative")
    if max_rel_allowed is not None:
        max_rel_allowed = float(max_rel_allowed)
        if max_rel_allowed < 0:
            failures.append("max_relative must be non-negative")

    minimum_cases = int(raw.get("minimum_cases", 2))
    if minimum_cases < 2:
        failures.append("minimum_cases must be >= 2")
    if len(cases) < minimum_cases:
        warnings.append(
            f"only {len(cases)} valid case(s); minimum_cases={minimum_cases}"
        )

    mode = str(raw.get("comparison", "reference")).lower()
    comparisons: list[tuple[int, int]] = []
    if len(cases) >= 2:
        if mode == "reference":
            ref_label = str(raw.get("reference", cases[0]["label"]))
            ref_indices = [i for i, c in enumerate(cases) if c["label"] == ref_label]
            if not ref_indices:
                failures.append(f"reference case not found: {ref_label}")
            else:
                r = ref_indices[0]
                comparisons = [(r, i) for i in range(len(cases)) if i != r]
        elif mode == "successive":
            comparisons = [(i, i + 1) for i in range(len(cases) - 1)]
        elif mode == "pairwise":
            comparisons = list(itertools.combinations(range(len(cases)), 2))
        else:
            failures.append("comparison must be reference, successive, or pairwise")

    rows = []
    max_abs = 0.0
    max_rel = 0.0
    for a_i, b_i in comparisons:
        try:
            abs_diff, rel_diff = _distance(cases[a_i]["value"], cases[b_i]["value"])
        except ValueError as exc:
            failures.append(str(exc))
            break
        max_abs = max(max_abs, abs_diff)
        max_rel = max(max_rel, rel_diff)
        rows.append({
            "a": cases[a_i]["label"],
            "b": cases[b_i]["label"],
            "absolute_difference": abs_diff,
            "symmetric_relative_difference": rel_diff,
        })

    threshold_failures = []
    if max_abs_allowed is not None and max_abs > max_abs_allowed:
        threshold_failures.append(
            f"max absolute difference {max_abs:g} exceeds {max_abs_allowed:g}"
        )
    if max_rel_allowed is not None and max_rel > max_rel_allowed:
        threshold_failures.append(
            f"max relative difference {max_rel:g} exceeds {max_rel_allowed:g}"
        )

    if raw.get("require_nonincreasing_successive_drift", False):
        if mode != "successive":
            failures.append(
                "require_nonincreasing_successive_drift requires comparison=successive"
            )
        else:
            rel_series = [row["symmetric_relative_difference"] for row in rows]
            tol = float(raw.get("drift_monotonicity_slack", 0.0))
            for prev, nxt in zip(rel_series, rel_series[1:]):
                if nxt > prev + tol:
                    threshold_failures.append(
                        "successive relative drift increases toward the requested limit"
                    )
                    break

    diagnostic_only = max_abs_allowed is None and max_rel_allowed is None
    if diagnostic_only:
        warnings.append(
            "no preregistered max_absolute/max_relative threshold; result is diagnostic only"
        )

    if failures or threshold_failures:
        status = "FAIL"
    elif len(cases) < minimum_cases or diagnostic_only:
        status = "PARTIAL"
    else:
        status = "PASS"

    all_failures = failures + threshold_failures
    if status == "PASS":
        note = (
            f"{kind} robustness passed across {len(cases)} case(s); "
            f"max symmetric relative difference={max_rel:.6g}."
        )
    elif status == "PARTIAL":
        note = (
            f"{kind or 'unspecified'} robustness is partial: "
            + (warnings[0] if warnings else "diagnostic-only scan")
        )
    else:
        note = (
            f"{kind or 'unspecified'} robustness failed: "
            + (all_failures[0] if all_failures else "unknown failure")
        )

    return {
        "id": evidence_id,
        "obligation": obligation,
        "status": status,
        "engine": f"robustness-{kind or 'unknown'}",
        "artifact": artifact or str(path),
        "note": note,
        "metadata": {
            "adapter": "theorygate.adapters.robustness",
            "kind": kind,
            "spec": str(path),
            "spec_sha256": _sha256(path) if path.is_file() else None,
            "observable": raw.get("observable"),
            "comparison": mode,
            "reference": raw.get("reference"),
            "thresholds": {
                "max_absolute": max_abs_allowed,
                "max_relative": max_rel_allowed,
            },
            "minimum_cases": minimum_cases,
            "cases": cases,
            "comparisons": rows,
            "max_absolute_difference": max_abs,
            "max_symmetric_relative_difference": max_rel,
            "diagnostic_only": diagnostic_only,
            "failures": all_failures,
            "warnings": warnings,
        },
    }


def write_evidence_json(evidence: dict, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
