# QCCG × RFQG bridge pilot

This directory is a deliberately scoped TheoryGate field test for the proposed
QCCG microscopic / RFQG-5 continuum connection.

It does **not** claim that QCCG already derives general relativity.

The first pilot checks only:

1. a finite local Weyl register;
2. the small-phase quadratic limit of the exact finite-Weyl local term;
3. a declared periodic quadratic tensor Hessian with two massless branches;
4. preregistered (1/L) finite-size scaling of the first tensor excitation;
5. persistence of declared gapped defect sectors;
6. the conditional algebra (2=D-2\Rightarrow D=4) under the separately
   declared geometric-reciprocity model choice.

TheoryGate is intentionally configured so those checks can promote only
`QCCG_QUADRATIC_TT_TOY`.

The physically stronger claims remain blocked until independent evidence exists
for:

- derivation from one explicit interacting finite-qudit parent Hamiltonian;
- a smooth 3+1 Lorentzian continuum phase;
- common matter/gravity Lorentz universality;
- continuum diffeomorphism/BRST identities;
- physical unitarity of the scaling limit;
- matching to the RFQG-5/asymptotic-safety universality class;
- the GR infrared effective action;
- real-time strong-gravity dynamics.

## Run

```bash
python qccg/run_quadratic_audit.py \
  --out artifacts/qccg/evidence.json \
  --summary artifacts/qccg/summary.json

theorygate validate qccg/theorygate.yaml

theorygate check qccg/theorygate.yaml \
  --evidence artifacts/qccg/evidence.json \
  --require QCCG_QUADRATIC_TT_TOY

theorygate check qccg/theorygate.yaml \
  --evidence artifacts/qccg/evidence.json \
  --json
```

The last report should support the scoped quadratic claim while keeping
`QCCG_EMERGENT_MASSLESS_SPIN2`, `QCCG_RFQG_UNIVERSALITY`,
`QCCG_GR_IR`, and `QCCG_STRONG_GRAVITY` blocked.
