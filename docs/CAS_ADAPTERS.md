# CAS evidence adapters

TheoryGate supports four symbolic evidence paths:

- **SymPy**: TheoryGate directly evaluates declared symbolic identities.
- **xAct**: a Wolfram/xAct script runs under an explicit PASS/FAIL marker contract.
- **Cadabra**: a Cadabra script runs under the same contract.
- **Maxima / generic external CAS**: script-backed engines use the same provenance format.

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

## Script-backed CAS contract

xAct, Cadabra, Maxima, and generic external CAS engines use the same rule:

1. the script exits successfully;
2. it does not emit the configured fail marker;
3. it emits the configured pass marker only after all intended symbolic assertions pass.

Default markers:

```text
THEORYGATE:PASS
THEORYGATE:FAIL
```

TheoryGate records:

- exact executable and command argument vector;
- tool-version command/output;
- script SHA-256;
- exit code;
- stdout/stderr tails;
- engine label and marker policy.

The domain-specific script owns the actual symbolic assertion. TheoryGate owns execution
provenance and downstream claim gating.

## xAct

```bash
theorygate evidence cas xact \
  --script audit/rederive_bianchi_ix.wls \
  --id xact-bianchi-ix \
  --obligation GR_REDUCTION_ALGEBRA \
  --output artifacts/xact-bianchi-ix.json \
  --require-pass
```

Default command:

```bash
wolframscript -file audit/rederive_bianchi_ix.wls
```

## Cadabra

```bash
theorygate evidence cas cadabra \
  --script audit/rederive_curvature.cdb \
  --id cadabra-curvature \
  --obligation CURVATURE_IDENTITY \
  --output artifacts/cadabra-curvature.json \
  --require-pass
```

Default command:

```bash
cadabra2 audit/rederive_curvature.cdb
```

## Maxima

Maxima has a built-in preset so an independent `ctensor` backend can produce the same
standard evidence shape:

```bash
theorygate evidence cas maxima \
  --script cas/maxima/bianchi_ix_reduction.mac \
  --id maxima-bianchi-ix \
  --obligation GR_REDUCTION_ALGEBRA \
  --output artifacts/maxima-bianchi-ix.json \
  --require-pass
```

The default invocation uses Maxima's documented batch/quiet/error-exit options:

```text
maxima --quiet --quit-on-error --batch=<script>
```

and records `maxima --version`.

The Maxima script must print `THEORYGATE:PASS` only after its own checks succeed.

## Generic external CAS

Other CAS systems can use the same adapter without adding a new TheoryGate backend.

Example shape:

```bash
theorygate evidence cas external \
  --engine reduce \
  --executable redcsl \
  --script audit/reduction.in \
  --command-arg=--batch \
  --command-arg='{script}' \
  --version-arg=--version \
  --id reduce-reduction \
  --obligation GR_REDUCTION_ALGEBRA \
  --output artifacts/reduce-reduction.json \
  --require-pass
```

`{script}` is replaced with the absolute script path. If no `{script}` token appears,
TheoryGate appends the script path to the command.

Arguments are executed as an argument vector, not through a shell. For values beginning
with `-`, use the `--command-arg=--flag` / `--version-arg=--flag` form so
`argparse` does not interpret the value as a TheoryGate option.

A generic engine requires an explicit executable. The arbitrary engine label is stored in
the evidence record but does not grant extra trust.

## Why this is script-driven

TheoryGate should not pretend that arbitrary GR tensor calculations can be reduced to a
single generic `simplify(lhs-rhs)` call. Model-specific tensor declarations,
canonicalization, variational rules, component choices, and sign conventions belong in
the audit script.

That separation also makes independent backends useful: two different CAS programs can
discharge separate obligations or provide multiple evidence records for the same
obligation without pretending they are mathematically independent proofs by default.
