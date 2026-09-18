# Physical claim templates

TheoryGate ships conservative **starter policies** for several high-risk physical
interpretations:

- `HISTORY_PROBABILITY`
- `PHYSICAL_OBSERVABLE`
- `TIMELESS_CLASS_OPERATOR`
- `SINGULARITY_RESOLUTION`

They are not declarations of universal scientific consensus. They are scaffolding for
making normally implicit obligations visible.

List them:

```bash
theorygate template list
```

Inspect one:

```bash
theorygate template show SINGULARITY_RESOLUTION
```

Create a model skeleton:

```bash
theorygate template init SINGULARITY_RESOLUTION \
  --model-id bianchi-ix-wdw \
  --title "Bianchi IX singularity-resolution audit" \
  --output theorygate.yaml
```

Then edit every obligation so it states the actual model-specific scope.

## HISTORY_PROBABILITY

The starter gate requires:

- class operator defined;
- projector family defined;
- physical inner product;
- decoherence;
- regulator stability;
- boundary robustness.

This is designed to stop a diagonal branch norm from being silently renamed an ordinary
additive probability.

## PHYSICAL_OBSERVABLE

The starter gate requires:

- observable operator definition;
- operator/domain definition;
- physical inner product;
- measurement rule or self-adjointness obligation appropriate to the model;
- semiclassical correspondence;
- clock robustness;
- factor-ordering robustness;
- regulator stability;
- boundary robustness.

This is intentionally stricter than "the numerical expectation value is finite."

## TIMELESS_CLASS_OPERATOR

The starter gate requires:

- constraint operator defined;
- class operator defined;
- class operator / constraint compatibility;
- physical inner product;
- regulator stability;
- boundary robustness.

This is aimed at preventing a finite-clock sequential projection construction from being
promoted to a timeless physical class operator without the missing bridge.

## SINGULARITY_RESOLUTION

The starter gate requires:

- an explicit singularity-resolution criterion;
- a physical observable relevant to that criterion;
- observable domain;
- physical inner product;
- evidence that the stated criterion is satisfied;
- semiclassical correspondence;
- clock robustness;
- ordering robustness;
- regulator stability;
- boundary robustness.

The exact criterion may instead be geodesic completeness, bounded relational
observables, extendibility, or something else. TheoryGate therefore does not hard-code a
single definition of "singularity resolution." The template requires the project to
state which definition it is using.

## Template discipline

A generated template contains descriptions reminding the user to replace generic
language with model-specific statements. A template should not be treated as passed
simply because every placeholder obligation has some evidence attached.

The intended workflow is:

```text
template
   |
   v
model-specific obligation rewrite
   |
   v
formal / CAS / robustness / numerical evidence
   |
   v
claim promotion
```
