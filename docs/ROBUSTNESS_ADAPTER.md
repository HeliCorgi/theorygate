# Robustness evidence adapter

The robustness adapter covers four explicit sensitivity axes:

- `regulator`
- `clock`
- `ordering`
- `boundary`

All four use the same data format. TheoryGate does **not** invent scientific tolerances.
A scan without a preregistered absolute or relative threshold is diagnostic and returns
`PARTIAL`, never `PASS`.

## Clock example

```json
{
  "kind": "clock",
  "observable": "branch_weight",
  "comparison": "reference",
  "reference": "clock-A",
  "thresholds": {
    "max_relative": 0.05
  },
  "minimum_cases": 3,
  "cases": [
    {"label": "clock-A", "value": 0.300},
    {"label": "clock-B", "value": 0.304},
    {"label": "clock-C", "value": 0.297}
  ]
}
```

Run:

```bash
theorygate evidence robustness \
  --spec clock-scan.json \
  --id clock-robustness \
  --obligation CLOCK_ROBUSTNESS \
  --output artifacts/clock-robustness.json \
  --require-pass
```

## Comparison modes

### reference

Every case is compared with the named `reference`. If omitted, the first case is the
reference.

### successive

Cases are compared in order:

```text
case0 -> case1
case1 -> case2
...
```

This is useful for regulator limits such as box size, grid spacing, cutoff, or `eta`.

### pairwise

All case pairs are compared. This is often useful for unordered choices such as factor
orderings or alternative clocks.

## Metrics

For scalar or equal-length vector values, TheoryGate records:

- maximum absolute component difference;
- maximum symmetric relative component difference,

where the symmetric relative difference is

```text
2 |a-b| / (|a| + |b|)
```

with zero assigned when both values are zero.

Available thresholds:

```json
{
  "thresholds": {
    "max_absolute": 1e-6,
    "max_relative": 0.05
  }
}
```

If both are supplied, both must pass.

The tolerance is part of the research protocol. TheoryGate records and applies it; it
does not decide that 5%, 1%, or any other threshold is scientifically appropriate.

## Regulator convergence direction

For an ordered `successive` scan, this optional check can reject a sequence whose
successive relative drift grows toward the intended limit:

```json
{
  "kind": "regulator",
  "comparison": "successive",
  "require_nonincreasing_successive_drift": true,
  "drift_monotonicity_slack": 0.001,
  "thresholds": {"max_relative": 0.2},
  "cases": [
    {"label": "eta=.1", "setting": 0.1, "value": 1.00},
    {"label": "eta=.05", "setting": 0.05, "value": 1.01},
    {"label": "eta=.025", "setting": 0.025, "value": 1.05}
  ]
}
```

That example fails because the later step moves farther, not closer.

This is still a finite scan, not a convergence proof. A PASS discharges only the
obligation stated for that finite protocol.

## Status behavior

- `PASS`: enough cases, thresholds explicitly provided, all configured checks pass.
- `FAIL`: malformed scientific scan or configured threshold/trend violation.
- `PARTIAL`: valid diagnostics but insufficient case count or no declared threshold.

The complete cases, comparisons, thresholds, maximum differences, spec hash, warnings,
and failures are preserved in the evidence metadata.
