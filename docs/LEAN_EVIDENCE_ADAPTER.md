# Lean evidence adapter

TheoryGate's Lean adapter turns a concrete Lean/Lake verification run into a
TheoryGate `evidence` record.

It is a **formal-evidence adapter for physical claim audits**. It does not turn
a theorem into experimental evidence and it does not decide whether the theorem's
assumptions describe nature.

## What it records

For a selected Lean project and declaration set, the adapter records:

- exact git commit SHA, branch, remote, and working-tree cleanliness;
- `lake --version` and `lake env lean --version`;
- SHA-256 hashes of `lean-toolchain`, `lake-manifest.json`, and Lake config files
  when present;
- the exact `lake build` command and exit code;
- generated audit imports;
- each fully qualified theorem name;
- `#print axioms` results per theorem;
- forbidden/unexpected axiom policy results;
- command-output tails for diagnosis.

The generated JSON is already shaped as one TheoryGate evidence object.

## Example: astra-blackhole

From a checkout where `theorygate` is installed:

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

The adapter creates temporary Lean source equivalent to:

```lean
import AstraBlackhole

#check AstraBlackhole.time_dependent_factorization_residual
#print axioms AstraBlackhole.time_dependent_factorization_residual
```

for each declaration separately and parses Lean's own output.

## Axiom policy

By default:

- every reported axiom is recorded;
- `sorryAx` is forbidden;
- other axioms do **not** automatically fail the gate.

To require an explicit allow-list:

```bash
theorygate evidence lean ... \
  --allow-axiom propext \
  --allow-axiom Classical.choice \
  --allow-axiom Quot.sound
```

Any other reported axiom then makes the evidence `FAIL`.

To require no axioms:

```bash
theorygate evidence lean ... --no-axioms
```

Additional forbidden names can be supplied with repeated `--forbid-axiom`.

## Git provenance rule

A clean git tree is required for `PASS` because a commit SHA must identify the
source that was compiled.

A dirty tree therefore yields `FAIL` by default. `--allow-dirty` exists for
interactive development, but such evidence is always `PARTIAL`, never `PASS`.

This is intentional: "the build passed at commit X" is false provenance when
uncommitted source participated in the build.

## Build scope

With no `--build-target`, the adapter runs:

```bash
lake build
```

Repeated targets narrow the build scope:

```bash
--build-target AstraBlackhole --build-target Audit
```

The exact targets are stored in evidence metadata. A targeted build should only
discharge an obligation whose scope matches that target.

## CI behavior

Evidence generation itself returns exit code 0 even when the evidence says
`FAIL` or `PARTIAL`; negative evidence is a valid artifact.

Add `--require-pass` when the formal obligation is a required CI gate. Then any
non-`PASS` evidence exits 1.

This mirrors TheoryGate's main design: record evidence first, promote a claim only
when the corresponding obligation requires it.
