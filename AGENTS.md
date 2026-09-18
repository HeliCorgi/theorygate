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

- Robustness adapters must never invent scientific tolerances. Missing preregistered thresholds produce PARTIAL, not PASS.
- Script-backed CAS adapters (xAct/Cadabra/Maxima/generic external) use explicit marker contracts; a successful process without the required PASS marker is not evidence of a passed symbolic assertion.
- Built-in physical claim templates are conservative scaffolding. Rewrite generic obligations to the model-specific physical statement before using them as publication gates.

- Broad-plateau scans must distinguish fixed/preregistered criteria from post-hoc exploratory window selection. Exploratory plateau discovery cannot produce PASS.
- Insufficient plateau sampling is PARTIAL rather than FAIL; enough sampled cases with no qualifying plateau may produce FAIL under the declared protocol.
