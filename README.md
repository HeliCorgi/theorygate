# TheoryGate

**TheoryGate is a physical-claim audit and promotion-gate engine for computational and formal physics.**

It does **not** decide whether a physical theory is true. It records explicit model
choices, expands physical claims into checkable obligations, attaches evidence from
formal proofs / CAS / numerical audits / robustness scans, and reports the strongest
claim currently supported by that evidence.

The core data model is intentionally domain-generic, but the project is aimed at
questions such as:

- is this quantity only model-internal, or can it be called a physical observable?
- is a branch weight actually a probability?
- is a result regulator / boundary / clock / ordering independent?
- does a formal derivation prove the algebra claimed under the stated assumptions?
- which stronger physical interpretation is still blocked, and by what?

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

- `lean` -- formal theorem/proof evidence;
- `xact`, `cadabra`, `sympy` -- symbolic derivation cross-checks;
- `numerical-audit` -- convergence, conservation, recombination, residual tests;
- `robustness-scan` -- clock, ordering, regulator, boundary and discretization scans;
- `literature` -- provenance for assumptions or known limiting cases.

An engine name is provenance, **not trust by declaration**.

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

## Lean evidence adapter

v0.2 can execute a Lean/Lake project and turn the result directly into one
TheoryGate evidence record.

For example, against `astra-blackhole`:

```bash
theorygate evidence lean \
  --project ../astra-blackhole/lean \
  --id bianchi-factorization-lean \
  --obligation WDW_FACTORIZATION_ALGEBRA \
  --import AstraBlackhole \
  --theorem AstraBlackhole.time_dependent_factorization_residual \
  --theorem AstraBlackhole.common_operator_preserves_recombination \
  --output artifacts/bianchi-factorization-lean.json \
  --require-pass
```

The adapter records:

- exact git commit SHA, branch, remote and dirty/clean state;
- Lean and Lake versions;
- SHA-256 hashes of the pinned toolchain / Lake files;
- exact `lake build` scope and result;
- generated theorem audit imports;
- theorem-by-theorem `#print axioms` results;
- forbidden or unexpected axiom findings.

`sorryAx` is forbidden by default.

A clean git tree is required for `PASS`. A dirty tree does not have commit-complete
provenance, so it is `FAIL` unless `--allow-dirty` is explicitly used; even then the
evidence is only `PARTIAL`, never `PASS`.

For an explicit axiom allow-list:

```bash
theorygate evidence lean ... \
  --allow-axiom propext \
  --allow-axiom Classical.choice \
  --allow-axiom Quot.sound
```

Or require no axioms:

```bash
theorygate evidence lean ... --no-axioms
```

See [docs/LEAN_EVIDENCE_ADAPTER.md](docs/LEAN_EVIDENCE_ADAPTER.md).

The adapter verifies a formal obligation at the theorem's actual scope. It does **not**
turn a theorem about a chosen clock, quantization or inner product into evidence that
that choice is physically unique or empirically correct.

## Evidence ingestion

Adapter output can now be consumed directly during claim evaluation:

```bash
theorygate check theorygate-model.yaml \
  --evidence artifacts/bianchi-factorization-lean.json
```

Multiple evidence artifacts and quoted globs are supported:

```bash
theorygate check theorygate-model.yaml \
  --evidence 'artifacts/formal/*.json' \
  --evidence 'artifacts/robustness/*.yaml' \
  --require MODEL_INTERNAL_RESULT
```

External evidence may be a single evidence object, a list, or a bundle with an
`evidence` field. The source filename is recorded in
`metadata.theorygate_ingested_from`.

Duplicate evidence IDs are rejected by default. Explicit replacement requires
`--replace-evidence`; evidence targeting an obligation not declared by the model is
always rejected. Negative evidence such as `FAIL` or `PARTIAL` is ingested normally
and can block promotion.

See [docs/EVIDENCE_INGESTION.md](docs/EVIDENCE_INGESTION.md).


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
7. **Formal provenance must identify compiled source.** A dirty tree cannot produce
   commit-complete `PASS` evidence.

## Why this exists

Research with AI agents makes it cheap to generate derivations, code and plausible
interpretations. It does not make the distinctions between

- theorem and assumption,
- finite discretization and continuum statement,
- model-internal observable and physical observable,
- regulator-dependent result and regulator-independent result,
- branch weight and probability,
- a consistent quantization and a uniquely justified physical quantization,

go away.

TheoryGate is intended to make those distinctions executable.

## Roadmap

v0.1: schema + dependency evaluation + claim promotion + CLI.

v0.2: Lean evidence adapter with git/toolchain/axiom provenance.

v0.3: external evidence ingestion into claim evaluation, including glob loading and explicit replacement policy.

Likely next layers:

- symbolic adapters for xAct/Cadabra/SymPy canonical-form comparison;
- numerical/robustness adapters, potentially reusing the trajectory/axis ideas from
  `stateflow`;
- signed evidence bundles and stronger artifact-integrity checks;
- physical-claim templates for quantum mechanics, GR/minisuperspace, QFT and
  semiclassical gravity;
- GitHub Actions summary / PR annotation;
- evidence DAG visualization.

## Non-goals

TheoryGate is **not**:

- a proof assistant;
- a quantum-gravity truth machine;
- a replacement for experimental evidence;
- a guarantee that a chosen model corresponds to nature;
- a license to call a numerically stable quantity an observable or probability.

It is a physical-claim scope and promotion checker.

## License

Apache License 2.0. Copyright 2026 HeliCorgi.
