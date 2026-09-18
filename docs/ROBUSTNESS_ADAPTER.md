# Robustness evidence adapter

The robustness adapter covers four explicit sensitivity axes:

- `regulator`
- `clock`
- `ordering`
- `boundary`

TheoryGate does **not** invent scientific tolerances. A scan without a preregistered
relevant threshold is diagnostic and returns `PARTIAL`, never `PASS`.

## Standard comparison modes

### reference

Every case is compared with the named reference.

### successive

Cases are compared in order. This is useful for genuine directed limits such as
`h -> 0`, `eta -> 0+`, grid refinement, or box enlargement.

### pairwise

All case pairs are compared. This is useful for unordered choices such as clocks or
factor orderings.

For scalar or equal-length vector values, TheoryGate records maximum absolute component
difference and maximum symmetric relative component difference,

```text
2 |a-b| / (|a| + |b|)
```

with zero when both values are zero.

## Broad plateau mode

Some regulators are not directed limits. Complex absorbing potential strength is a
typical example: too weak may fail to absorb, while too strong may enter a
reflection/Zeno regime. A narrow tuned optimum should not be promoted to a
regulator-independent result.

Use:

```json
{
  "kind": "regulator",
  "observable": "max_abs_Doff",
  "comparison": "plateau",
  "plateau_selection": "criterion",
  "minimum_plateau_cases": 3,
  "minimum_setting_span": 0.02,
  "thresholds": {
    "max_relative_within_plateau": 0.05
  },
  "cases": [
    {"label": ".025", "setting": 0.025, "value": 0.11048},
    {"label": ".040", "setting": 0.040, "value": 0.05358},
    {"label": ".050", "setting": 0.050, "value": 0.03210},
    {"label": ".060", "setting": 0.060, "value": 0.01666},
    {"label": ".075", "setting": 0.075, "value": 0.00733},
    {"label": ".085", "setting": 0.085, "value": 0.01361},
    {"label": ".100", "setting": 0.100, "value": 0.02323}
  ]
}
```

With a 5% within-plateau tolerance, the example fails: there is no contiguous broad
window satisfying the declared count/span/variation rule. A single minimum near
`.075` is therefore not sufficient.

Plateau cases require numeric `setting` values.

Available plateau thresholds:

```json
{
  "thresholds": {
    "max_absolute_within_plateau": 1e-3,
    "max_relative_within_plateau": 0.05
  }
}
```

The ordinary `max_absolute` / `max_relative` names are also accepted as fallbacks in
plateau mode.

### plateau_selection = fixed

Use a window fixed before the result is interpreted:

```json
{
  "comparison": "plateau",
  "plateau_selection": "fixed",
  "plateau_window": {
    "min_setting": 0.04,
    "max_setting": 0.08
  },
  "minimum_plateau_cases": 3,
  "minimum_setting_span": 0.02,
  "thresholds": {
    "max_relative_within_plateau": 0.05
  }
}
```

The selected cases inside that window must meet the case-count, actual setting-span, and
variation requirements. A valid fixed window can produce `PASS`.

### plateau_selection = criterion

The existence of any contiguous window satisfying the predeclared case-count, setting
span, and variation criterion is the protocol. This can produce `PASS`.

This mode is appropriate only when the existence criterion itself was chosen before
inspecting the result. TheoryGate records the mode but cannot prove when the protocol was
authored.

### plateau_selection = exploratory

TheoryGate searches the observed data for qualifying windows but **never promotes the
result to PASS**. If a stable window exists, the evidence is `PARTIAL`; if enough data
were scanned and no qualifying window exists, it is `FAIL`.

This is the conservative option for post-hoc exploration.

If `plateau_selection` is omitted, a supplied `plateau_window` defaults to `fixed`;
otherwise the mode defaults to `exploratory`.

## Insufficient data versus negative evidence

TheoryGate distinguishes:

- **PARTIAL**: fewer than `minimum_plateau_cases` valid cases, no declared tolerance,
  or a qualifying window found only through exploratory selection;
- **FAIL**: enough data were provided but no broad plateau satisfies the declared
  criterion, or the configured fixed window violates it;
- **PASS**: a fixed or criterion-based preregistered plateau rule is satisfied.

This separation prevents “not enough scan” from being reported as evidence against a
plateau.

## Directed regulator convergence

The older directed-limit check remains available:

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

That rule should not be used merely because it makes a non-monotone regulator fail; use
`comparison=plateau` when a broad stable region is the actual scientific criterion.

## Scope

A robustness PASS is still a finite protocol, not a convergence theorem or proof of
regulator independence in the continuum. The evidence records the spec hash, cases,
candidate/stable plateau windows, selected window, thresholds, warnings, and failures.
