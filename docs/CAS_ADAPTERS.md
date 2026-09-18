# CAS evidence adapters

TheoryGate v0.4 supports three symbolic evidence paths:

- **SymPy**: TheoryGate directly evaluates declared symbolic identities.
- **xAct**: TheoryGate executes a Wolfram/xAct audit script and requires an explicit marker.
- **Cadabra**: TheoryGate executes a Cadabra audit script and requires an explicit marker.

CAS evidence is symbolic evidence only. A successful tensor identity or reduction does
not establish that the selected action, gauge, quantization, clock, factor ordering, or
boundary condition is physically unique.

## SymPy

Example spec:

```json
{
  "symbols": {
    "x": {"real": true}
  },
  "checks": [
    {
      "id": "trig",
      "lhs": "sin(x)**2 + cos(x)**2",
      "rhs": "1",
      "method": "trigsimp"
    }
  ]
}
```

Run:

```bash
theorygate evidence cas sympy \
  --spec symbolic-audit.json \
  --id symbolic-gr-check \
  --obligation GR_REDUCTION_ALGEBRA \
  --output artifacts/symbolic-gr-check.json \
  --require-pass
```

Supported reduction methods are currently:

- `simplify`
- `cancel`
- `trigsimp`
- `expand`
- `factor`
- `together`

The evidence records the SymPy version, spec SHA-256, every check, and its reduced
difference.

### Security

SymPy expression specs are **trusted local research inputs**. SymPy expression parsing is
not treated as a sandbox. Do not feed untrusted network input directly to this adapter.

## xAct

xAct checks are deliberately script-driven because a useful GR audit generally requires
model-specific tensor declarations, metrics, contractions, canonicalization rules, and
sometimes variational calculations.

Write a Wolfram script which exits normally and prints:

```text
THEORYGATE:PASS
```

only after all intended xAct checks pass. On a failed assertion it should emit:

```text
THEORYGATE:FAIL
```

or exit non-zero.

Then:

```bash
theorygate evidence cas xact \
  --script audit/rederive_bianchi_ix.wls \
  --id xact-bianchi-ix \
  --obligation GR_REDUCTION_ALGEBRA \
  --output artifacts/xact-bianchi-ix.json \
  --require-pass
```

The default command is:

```bash
wolframscript -file audit/rederive_bianchi_ix.wls
```

Use `--executable` to select another WolframScript binary.

TheoryGate records the exact command, tool-version output, script SHA-256, exit code, and
stdout/stderr tails.

## Cadabra

The contract is the same:

```bash
theorygate evidence cas cadabra \
  --script audit/rederive_curvature.cdb \
  --id cadabra-curvature \
  --obligation CURVATURE_IDENTITY \
  --output artifacts/cadabra-curvature.json \
  --require-pass
```

The default command is:

```bash
cadabra2 audit/rederive_curvature.cdb
```

The script must emit `THEORYGATE:PASS` only after its own symbolic assertions pass.

## Why xAct/Cadabra are script contracts

TheoryGate should not pretend that arbitrary GR tensor calculations can be reduced to a
single generic `simplify(lhs-rhs)` call. The domain-specific CAS script owns the actual
mathematical assertion. TheoryGate owns:

- exact execution provenance;
- script hashing;
- tool/version recording;
- required PASS/FAIL marker policy;
- conversion to a standard evidence object;
- downstream physical claim gating.

That separation is intentional.
