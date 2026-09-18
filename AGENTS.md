# TheoryGate development rules

TheoryGate is a scope and claim-promotion checker. It is not a truth oracle.

- Keep model choices, assumptions, evidence and claims distinct.
- Never convert reproducibility, compilation, symbolic simplification or numerical stability into physical validity by implication.
- Negative evidence (`FAIL`, `PARTIAL`, `OPEN`) is a valid product outcome.
- Adding an adapter for Lean/CAS/numerics must record exactly what was executed, its revision/tool version, and the artifact used as evidence.
- A theorem proved under assumptions discharges only the obligation stated under those assumptions.
- A finite-grid or finite-regulator check does not discharge a continuum or regulator-independent obligation unless the obligation explicitly says so.
- Do not weaken a claim requirement merely to make a sample pass.
- Tests should include blocked promotions, not only successful claims.
- Preserve Apache-2.0 licensing and third-party notices.
