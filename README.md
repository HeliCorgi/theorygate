# TheoryGate

**TheoryGate is a claim-audit engine for computational and formal research.**

It does **not** decide whether a physical theory is true. It records explicit model
choices, expands scientific claims into checkable obligations, attaches evidence from
formal proofs / CAS / numerical audits / robustness scans, and reports the strongest
claim currently supported by that evidence.

The intended failure mode is conservative:

> a calculation may be reproducible and internally consistent while a stronger physical
> interpretation remains blocked.

TheoryGate makes that boundary machine-readable.

## Core model

```text
ModelSpec
   |
   +-- Obligation -------- Evidence
   |      |                  |
   |      +------------------+
   |
   +-- Claim --requires--> Obligation(s)
                |
                v
       SUPPORTED / BLOCKED
                |
                v
      strongest supported claim
```

Typical evidence engines include:

- `lean` -- theorem/proof evidence;
- `xact`, `cadabra`, `sympy` -- symbolic derivation cross-checks;
- `numerical-audit` -- convergence, conservation, recombination, residual tests;
- `robustness-scan` -- clock, ordering, regulator, boundary and discretization scans;
- `literature` -- provenance for assumptions or known limiting cases.

An engine name is provenance, **not trust by declaration**. TheoryGate v0.1 evaluates
the evidence records you give it; adapters that execute external engines belong in later
layers.

## Install

Python 3.10+.

```bash
pip install -e .
```

YAML input is supported through PyYAML. JSON is always valid input.

## Quick start

```bash
theorygate check examples/astra_blackhole.json
```

Example output:

```text
Model: Bianchi IX finite-clock history audit

Obligations
  COMMON_PROPAGATOR              PASS
  BRANCH_RECOMBINATION           PASS
  INNER_PRODUCT                  MODEL_CHOICE
  CLOCK                          MODEL_CHOICE
  DECOHERENCE                    FAIL
  REGULATOR_STABILITY            PARTIAL
  PHYSICAL_INNER_PRODUCT         OPEN
  CURVATURE_OBSERVABLE_4D        OPEN

Claims
  MODEL_INTERNAL_BRANCH_WEIGHT   SUPPORTED
  HISTORY_PROBABILITY            BLOCKED
  TIMELESS_PHYSICAL_CLASS_OP     BLOCKED
  SINGULARITY_RESOLUTION         BLOCKED

Strongest supported claim:
  MODEL_INTERNAL_BRANCH_WEIGHT
```

To make CI fail unless a particular claim is supported:

```bash
theorygate check examples/astra_blackhole.json --require HISTORY_PROBABILITY
```

Machine-readable report:

```bash
theorygate check examples/astra_blackhole.json --json
```

## Status vocabulary

Evidence uses a deliberately small vocabulary:

| status | meaning |
|---|---|
| `PASS` | the stated obligation is discharged at the recorded scope |
| `FAIL` | evidence contradicts / fails the obligation |
| `PARTIAL` | useful evidence exists but the obligation is not discharged |
| `OPEN` | explicitly unresolved |
| `MODEL_CHOICE` | declared modelling choice, not independently derived |
| `NOT_APPLICABLE` | the evidence item does not apply at this scope |

Computed obligations can additionally be `BLOCKED` when one of their prerequisite
obligations is not in an accepted state.

A claim declares exactly which statuses it accepts for every requirement. The default is
only `PASS`. A model-internal claim may explicitly accept `MODEL_CHOICE`; a physical
promotion can require a stricter `PASS`.

## Minimal document

```yaml
version: "0.1"
model:
  id: toy
  title: Toy model
  choices:
    clock: internal_t

obligations:
  - id: ALGEBRA
    title: Algebraic identity
    kind: formal

evidence:
  - id: lean-algebra
    obligation: ALGEBRA
    status: PASS
    engine: lean
    artifact: Formal/Toy.lean

claims:
  - id: TOY_CLAIM
    title: Toy claim
    rank: 10
    statement: The algebraic toy statement holds.
    requires:
      - ALGEBRA
```

Requirements can be expanded when non-`PASS` statuses are intentionally acceptable:

```yaml
requires:
  - id: INNER_PRODUCT
    accept: [PASS, MODEL_CHOICE]
```

This does not make a modelling choice a theorem. The generated report records the
accepted caveat.

## Design rules

1. **Claims are downstream of evidence.** A result file cannot silently promote itself.
2. **Model choices stay visible.** Clock, inner product, factor ordering, boundary
   conditions and regulators should not be smuggled into "verified" conclusions.
3. **Negative results are first-class.** `FAIL`, `PARTIAL` and `OPEN` are useful
   outputs, not errors to hide.
4. **Formal, symbolic and numerical evidence are distinct.** A CAS identity is not a
   convergence theorem; a Lean theorem under assumptions is not empirical validation.
5. **The strongest supported claim is computed, not narrated.**
6. **Reproducibility is not physical validity.** TheoryGate can record both.

## Why this exists

Research with AI agents makes it cheap to generate derivations, code and plausible
interpretations. It does not make the distinctions between

- theorem and assumption,
- finite discretization and continuum statement,
- model-internal observable and physical observable,
- regulator-dependent result and regulator-independent result,
- branch weight and probability,

go away.

TheoryGate is intended to make those distinctions executable.

## Roadmap

v0.1 is intentionally small: schema + dependency evaluation + claim promotion + CLI.

Likely next layers:

- evidence adapters that execute Lean and record theorem/axiom metadata;
- symbolic adapters for xAct/Cadabra/SymPy canonical-form comparison;
- numerical/robustness adapters, potentially reusing the trajectory/axis ideas from
  `stateflow`;
- evidence hashes and revision pinning;
- claim templates for quantum mechanics, GR/minisuperspace and PDE research;
- GitHub Actions summary / PR annotation;
- evidence DAG visualization.

## Non-goals

TheoryGate is **not**:

- a proof assistant;
- a quantum-gravity truth machine;
- a replacement for experimental evidence;
- a guarantee that a chosen model corresponds to nature;
- a license to call a numerically stable quantity an observable or probability.

It is a scope and promotion checker.

## License

Apache License 2.0. Copyright 2026 HeliCorgi.
