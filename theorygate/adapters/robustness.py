from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import yaml


VALID_KINDS = {"regulator", "clock", "ordering", "boundary"}
VALID_COMPARISONS = {"reference", "successive", "pairwise", "plateau"}
VALID_PLATEAU_SELECTIONS = {"fixed", "criterion", "exploratory"}


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


def _pairwise_window_metrics(cases: list[dict], indices: list[int]) -> dict:
    rows = []
    max_abs = 0.0
    max_rel = 0.0
    for a_i, b_i in itertools.combinations(indices, 2):
        abs_diff, rel_diff = _distance(cases[a_i]["value"], cases[b_i]["value"])
        max_abs = max(max_abs, abs_diff)
        max_rel = max(max_rel, rel_diff)
        rows.append({
            "a": cases[a_i]["label"],
            "b": cases[b_i]["label"],
            "absolute_difference": abs_diff,
            "symmetric_relative_difference": rel_diff,
        })
    settings = [float(cases[i]["setting"]) for i in indices]
    return {
        "labels": [cases[i]["label"] for i in indices],
        "indices": indices,
        "minimum_setting": min(settings),
        "maximum_setting": max(settings),
        "setting_span": max(settings) - min(settings),
        "case_count": len(indices),
        "max_absolute_difference": max_abs,
        "max_symmetric_relative_difference": max_rel,
        "comparisons": rows,
    }


def _plateau_threshold_pass(
    window: dict,
    *,
    max_abs_allowed: float | None,
    max_rel_allowed: float | None,
) -> bool:
    if (
        max_abs_allowed is not None
        and window["max_absolute_difference"] > max_abs_allowed
    ):
        return False
    if (
        max_rel_allowed is not None
        and window["max_symmetric_relative_difference"] > max_rel_allowed
    ):
        return False
    return True


def _best_plateau(windows: list[dict]) -> dict | None:
    if not windows:
        return None
    return sorted(
        windows,
        key=lambda w: (
            -w["setting_span"],
            -w["case_count"],
            w["max_symmetric_relative_difference"],
            w["max_absolute_difference"],
        ),
    )[0]


def _evaluate_plateau(
    raw: dict,
    cases: list[dict],
    thresholds: dict,
    failures: list[str],
    warnings: list[str],
) -> dict:
    min_cases = int(raw.get("minimum_plateau_cases", 3))
    min_span = float(raw.get("minimum_setting_span", 0.0))
    if min_cases < 2:
        failures.append("minimum_plateau_cases must be >= 2")
    if min_span < 0:
        failures.append("minimum_setting_span must be non-negative")

    for case in cases:
        setting = case.get("setting")
        if not isinstance(setting, (int, float)) or isinstance(setting, bool):
            failures.append(
                f"plateau comparison requires numeric setting for case {case['label']}"
            )
            continue
        setting = float(setting)
        if not math.isfinite(setting):
            failures.append(
                f"plateau comparison requires finite setting for case {case['label']}"
            )
        case["setting"] = setting

    p_abs = thresholds.get(
        "max_absolute_within_plateau",
        thresholds.get("max_absolute"),
    )
    p_rel = thresholds.get(
        "max_relative_within_plateau",
        thresholds.get("max_relative"),
    )
    if p_abs is not None:
        p_abs = float(p_abs)
        if p_abs < 0:
            failures.append("max_absolute_within_plateau must be non-negative")
    if p_rel is not None:
        p_rel = float(p_rel)
        if p_rel < 0:
            failures.append("max_relative_within_plateau must be non-negative")

    diagnostic_only = p_abs is None and p_rel is None
    if diagnostic_only:
        warnings.append(
            "no preregistered plateau variation threshold; plateau scan is diagnostic only"
        )

    selection = raw.get("plateau_selection")
    window_spec = raw.get("plateau_window")
    if selection is None:
        selection = "fixed" if window_spec is not None else "exploratory"
    selection = str(selection).lower()
    if selection not in VALID_PLATEAU_SELECTIONS:
        failures.append(
            "plateau_selection must be fixed, criterion, or exploratory"
        )

    insufficient_sampling = len(cases) < min_cases
    if insufficient_sampling:
        warnings.append(
            f"only {len(cases)} valid case(s); minimum_plateau_cases={min_cases}"
        )

    if failures:
        return {
            "status": "FAIL",
            "diagnostic_only": diagnostic_only,
            "selection": selection,
            "candidate_windows": [],
            "stable_windows": [],
            "selected_window": None,
            "max_absolute": 0.0,
            "max_relative": 0.0,
            "thresholds": {
                "max_absolute_within_plateau": p_abs,
                "max_relative_within_plateau": p_rel,
            },
            "minimum_plateau_cases": min_cases,
            "minimum_setting_span": min_span,
        }

    sorted_indices = sorted(range(len(cases)), key=lambda i: cases[i]["setting"])
    if selection != "fixed" and len(sorted_indices) >= 2:
        observed_span = (
            cases[sorted_indices[-1]]["setting"] - cases[sorted_indices[0]]["setting"]
        )
        if observed_span < min_span:
            insufficient_sampling = True
            warnings.append(
                f"observed setting span {observed_span:g} is below "
                f"minimum_setting_span={min_span:g}"
            )

    candidates: list[dict] = []
    fixed_coverage_partial = False

    if selection == "fixed":
        if not isinstance(window_spec, dict):
            failures.append(
                "plateau_selection=fixed requires plateau_window with min_setting/max_setting"
            )
        else:
            try:
                low = float(window_spec["min_setting"])
                high = float(window_spec["max_setting"])
            except (KeyError, TypeError, ValueError):
                failures.append(
                    "plateau_window requires numeric min_setting and max_setting"
                )
            else:
                if high < low:
                    failures.append("plateau_window max_setting must be >= min_setting")
                indices = [
                    i for i in sorted_indices
                    if low <= cases[i]["setting"] <= high
                ]
                if indices:
                    candidates.append(_pairwise_window_metrics(cases, indices))
    else:
        for start in range(len(sorted_indices)):
            for end in range(start + min_cases, len(sorted_indices) + 1):
                indices = sorted_indices[start:end]
                window = _pairwise_window_metrics(cases, indices)
                if window["setting_span"] >= min_span:
                    candidates.append(window)

    stable = [
        w for w in candidates
        if w["case_count"] >= min_cases
        and w["setting_span"] >= min_span
        and _plateau_threshold_pass(
            w,
            max_abs_allowed=p_abs,
            max_rel_allowed=p_rel,
        )
    ]
    selected = _best_plateau(stable)

    if selection == "fixed":
        if candidates:
            fixed = candidates[0]
            if fixed["case_count"] < min_cases:
                fixed_coverage_partial = True
                warnings.append(
                    f"fixed plateau has {fixed['case_count']} case(s); "
                    f"minimum_plateau_cases={min_cases}"
                )
            if fixed["setting_span"] < min_span:
                fixed_coverage_partial = True
                warnings.append(
                    f"fixed plateau setting span {fixed['setting_span']:g} "
                    f"is below minimum_setting_span={min_span:g}"
                )
            if (
                p_abs is not None
                and fixed["max_absolute_difference"] > p_abs
            ):
                failures.append(
                    f"fixed plateau max absolute difference "
                    f"{fixed['max_absolute_difference']:g} exceeds {p_abs:g}"
                )
            if (
                p_rel is not None
                and fixed["max_symmetric_relative_difference"] > p_rel
            ):
                failures.append(
                    f"fixed plateau max relative difference "
                    f"{fixed['max_symmetric_relative_difference']:g} exceeds {p_rel:g}"
                )
        elif not failures:
            fixed_coverage_partial = True
            warnings.append("fixed plateau window contains no sampled cases")
    elif not stable and not diagnostic_only and not insufficient_sampling:
        failures.append(
            "no contiguous broad plateau satisfies the preregistered case/span/variation criteria"
        )

    if failures:
        status = "FAIL"
    elif insufficient_sampling or fixed_coverage_partial:
        status = "PARTIAL"
    elif diagnostic_only:
        status = "PARTIAL"
    elif selection == "exploratory":
        status = "PARTIAL"
        warnings.append(
            "stable plateau window was selected from observed data; exploratory search cannot PASS"
        )
    else:
        status = "PASS"

    if selected is None and candidates:
        selected = _best_plateau(candidates)

    return {
        "status": status,
        "diagnostic_only": diagnostic_only,
        "selection": selection,
        "candidate_windows": candidates,
        "stable_windows": stable,
        "selected_window": selected,
        "max_absolute": (
            0.0 if selected is None else selected["max_absolute_difference"]
        ),
        "max_relative": (
            0.0 if selected is None else selected["max_symmetric_relative_difference"]
        ),
        "thresholds": {
            "max_absolute_within_plateau": p_abs,
            "max_relative_within_plateau": p_rel,
        },
        "minimum_plateau_cases": min_cases,
        "minimum_setting_span": min_span,
    }


def collect_robustness_evidence(
    *,
    spec_path: str | Path,
    evidence_id: str,
    obligation: str,
    artifact: str | None = None,
) -> dict:
    """Evaluate a preregistered robustness scan.

    No tolerance is invented by TheoryGate. If the spec contains no relevant
    absolute or relative threshold, diagnostics are produced as PARTIAL rather
    than PASS.

    For non-monotone regulators, comparison=plateau supports a broad-plateau
    criterion instead of forcing a one-direction convergence interpretation.
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

    mode = str(raw.get("comparison", "reference")).lower()
    if mode not in VALID_COMPARISONS:
        failures.append(
            "comparison must be reference, successive, pairwise, or plateau"
        )

    if mode == "plateau":
        plateau = _evaluate_plateau(raw, cases, thresholds, failures, warnings)
        status = plateau["status"]
        all_failures = failures
        max_abs = plateau["max_absolute"]
        max_rel = plateau["max_relative"]
        comparisons = (
            [] if plateau["selected_window"] is None
            else plateau["selected_window"]["comparisons"]
        )
        diagnostic_only = plateau["diagnostic_only"]
        minimum_cases = int(raw.get("minimum_cases", 2))
        if status == "PASS":
            selected = plateau["selected_window"]
            note = (
                f"{kind} broad plateau passed across "
                f"{selected['case_count']} case(s), span={selected['setting_span']:.6g}; "
                f"max symmetric relative difference={max_rel:.6g}."
            )
        elif status == "PARTIAL":
            note = (
                f"{kind or 'unspecified'} plateau robustness is partial: "
                + (warnings[0] if warnings else "exploratory or diagnostic-only plateau")
            )
        else:
            note = (
                f"{kind or 'unspecified'} plateau robustness failed: "
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
                "reference": None,
                "thresholds": plateau["thresholds"],
                "minimum_cases": minimum_cases,
                "minimum_plateau_cases": plateau["minimum_plateau_cases"],
                "minimum_setting_span": plateau["minimum_setting_span"],
                "plateau_selection": plateau["selection"],
                "plateau_window": raw.get("plateau_window"),
                "cases": cases,
                "comparisons": comparisons,
                "candidate_windows": plateau["candidate_windows"],
                "stable_windows": plateau["stable_windows"],
                "selected_plateau": plateau["selected_window"],
                "max_absolute_difference": max_abs,
                "max_symmetric_relative_difference": max_rel,
                "diagnostic_only": diagnostic_only,
                "failures": all_failures,
                "warnings": warnings,
            },
        }

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

    comparisons_idx: list[tuple[int, int]] = []
    if len(cases) >= 2:
        if mode == "reference":
            ref_label = str(raw.get("reference", cases[0]["label"]))
            ref_indices = [i for i, c in enumerate(cases) if c["label"] == ref_label]
            if not ref_indices:
                failures.append(f"reference case not found: {ref_label}")
            else:
                r = ref_indices[0]
                comparisons_idx = [(r, i) for i in range(len(cases)) if i != r]
        elif mode == "successive":
            comparisons_idx = [(i, i + 1) for i in range(len(cases) - 1)]
        elif mode == "pairwise":
            comparisons_idx = list(itertools.combinations(range(len(cases)), 2))

    rows = []
    max_abs = 0.0
    max_rel = 0.0
    for a_i, b_i in comparisons_idx:
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
