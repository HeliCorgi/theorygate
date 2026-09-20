# QCCG literature anchors

This file records external results used as **comparison anchors**.  They do not
promote a QCCG claim by themselves.  QCCG-specific matching obligations still
require QCCG calculations.

## CDT effective transfer matrix

1. J. Ambjørn, J. Gizbert-Studnicki, A. Görlich, J. Jurkiewicz,
   **The transfer matrix in four-dimensional CDT**,
   JHEP 09 (2012) 017.
   - arXiv:1205.3791
   - DOI: 10.1007/JHEP09(2012)017
   - Use here: existence of an effective transfer matrix labelled only by the
     spatial three-volume / scale factor.

2. J. Ambjørn, J. Gizbert-Studnicki, A. Görlich, J. Jurkiewicz,
   **The effective action in 4-dim CDT. The transfer matrix approach**,
   JHEP 06 (2014) 034.
   - arXiv:1403.5940
   - DOI: 10.1007/JHEP06(2014)034
   - Use here: de Sitter-phase reduced transfer matrix / effective action.
     The reference kinetic structure is
     ```text
     (1/Gamma) * (n_{t+1}-n_t)^2 / (n_{t+1}+n_t)
     ```
     with the spherical-topology minisuperspace potential conventionally
     parametrized by an `n^(1/3)` curvature term plus a linear volume term.

3. J. Ambjørn, J. Gizbert-Studnicki, A. Görlich, D. Németh,
   **Is lattice quantum gravity asymptotically safe? Making contact between
   causal dynamical triangulations and the functional renormalization group**,
   Phys. Rev. D 110, 126006 (2024).
   - DOI: 10.1103/PhysRevD.110.126006
   - Use here: comparison of the CDT scale-factor effective action with FRG,
     identification of the generic infinite-volume de Sitter limit with an
     FRG Gaussian/IR fixed-point limit, and a prescription for discussing a
     putative UV lattice fixed point.
   - Important limitation: the paper explicitly states that the CDT data allow
     a UV fixed point but do not yet prove one.

## QCCG matching policy

External CDT/FRG results are anchors, not imported QCCG evidence.

The intended chain is

```text
QCCG microscopic dynamics
    -> QCCG reduced N3 transfer matrix
    -> CDT-like effective transfer dynamics
    -> CDT/FRG matching coordinates
    -> essential critical-exponent / universality comparison
    -> Reuter fixed-point match
```

A literature result can establish that a bridge or target exists.  It cannot
establish that QCCG lands on that target without a QCCG calculation.
