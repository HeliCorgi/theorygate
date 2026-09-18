from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .adapters.lean import LeanEvidenceConfig, collect_lean_evidence, write_evidence_json
from .evaluate import evaluate_document
from .io import DocumentError, load_document


def _print_report(report: dict) -> None:
    print(f"Model: {report['model']['title']}")
    print()
    print("Obligations")
    for oid, row in report["obligations"].items():
        print(f"  {oid:<32} {row['status']}")
        for blocker in row["blockers"]:
            print(f"    blocked by: {blocker}")
    print()
    print("Claims")
    claims = sorted(report["claims"].items(), key=lambda kv: (kv[1]["rank"], kv[0]))
    for cid, row in claims:
        verdict = "SUPPORTED" if row["supported"] else "BLOCKED"
        print(f"  {cid:<32} {verdict}")
        for caveat in row["caveats"]:
            print(f"    caveat: {caveat}")
        for blocker in row["blockers"]:
            print(f"    blocked by: {blocker}")
    print()
    print("Strongest supported claim:")
    print(f"  {report['strongest_supported_claim'] or 'NONE'}")


def _add_lean_evidence_parser(sub) -> None:
    evidence = sub.add_parser(
        "evidence",
        help="collect evidence from an external verification engine",
    )
    engines = evidence.add_subparsers(dest="evidence_engine", required=True)
    lean = engines.add_parser(
        "lean",
        help="run lake build and #print axioms, then emit TheoryGate evidence",
    )
    lean.add_argument("--project", required=True, help="Lean/Lake project directory")
    lean.add_argument("--id", required=True, dest="evidence_id", help="evidence id")
    lean.add_argument("--obligation", required=True, help="target TheoryGate obligation id")
    lean.add_argument(
        "--import",
        action="append",
        dest="imports",
        required=True,
        help="Lean module imported by the generated audit file; repeatable",
    )
    lean.add_argument(
        "--theorem",
        action="append",
        dest="theorems",
        required=True,
        help="fully qualified theorem/declaration to audit; repeatable",
    )
    lean.add_argument(
        "--build-target",
        action="append",
        default=[],
        help="optional lake build target; repeatable; default is full lake build",
    )
    lean.add_argument(
        "--allow-axiom",
        action="append",
        default=None,
        help=(
            "restrict #print axioms to this allow-list; repeatable. "
            "If omitted, axioms are recorded but only forbidden axioms fail the gate."
        ),
    )
    lean.add_argument(
        "--no-axioms",
        action="store_true",
        help="require audited declarations to depend on no axioms",
    )
    lean.add_argument(
        "--forbid-axiom",
        action="append",
        default=None,
        help="additional forbidden axiom; sorryAx is always forbidden by default",
    )
    lean.add_argument(
        "--allow-dirty",
        action="store_true",
        help="run on a dirty git tree; generated evidence is PARTIAL, never PASS",
    )
    lean.add_argument(
        "--artifact",
        help="override evidence artifact/provenance string",
    )
    lean.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="per-command timeout in seconds (default: 600)",
    )
    lean.add_argument(
        "--output",
        help="write evidence JSON to this path instead of stdout",
    )
    lean.add_argument(
        "--require-pass",
        action="store_true",
        help="exit 1 unless generated evidence status is PASS",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="theorygate",
        description="Audit evidence-to-claim promotion boundaries in physical research.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="evaluate obligations and claims")
    check.add_argument("path")
    check.add_argument("--json", action="store_true", dest="as_json")
    check.add_argument(
        "--require",
        metavar="CLAIM_ID",
        help="exit non-zero unless this claim is supported",
    )

    validate = sub.add_parser("validate", help="validate an audit document")
    validate.add_argument("path")

    _add_lean_evidence_parser(sub)
    return p


def _run_lean_evidence(args) -> int:
    if args.no_axioms and args.allow_axiom:
        print(
            "theorygate: --no-axioms cannot be combined with --allow-axiom",
            file=sys.stderr,
        )
        return 2

    allow_axioms = () if args.no_axioms else (
        None if args.allow_axiom is None else tuple(args.allow_axiom)
    )
    forbidden = ["sorryAx"]
    if args.forbid_axiom:
        forbidden.extend(args.forbid_axiom)

    config = LeanEvidenceConfig(
        project=Path(args.project),
        evidence_id=args.evidence_id,
        obligation=args.obligation,
        imports=tuple(args.imports),
        theorems=tuple(args.theorems),
        build_targets=tuple(args.build_target),
        allow_axioms=allow_axioms,
        forbid_axioms=tuple(dict.fromkeys(forbidden)),
        allow_dirty=bool(args.allow_dirty),
        timeout=float(args.timeout),
        artifact=args.artifact,
    )
    evidence = collect_lean_evidence(config)
    if args.output:
        write_evidence_json(evidence, args.output)
        print(f"{evidence['status']}: wrote {args.output}")
    else:
        print(json.dumps(evidence, indent=2, sort_keys=True))

    if args.require_pass and evidence["status"] != "PASS":
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "evidence":
        if args.evidence_engine == "lean":
            return _run_lean_evidence(args)
        return 2

    try:
        doc = load_document(args.path)
    except (OSError, ValueError, DocumentError) as exc:
        print(f"theorygate: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"valid: {args.path}")
        return 0

    report = evaluate_document(doc)
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_report(report)

    if args.require:
        row = report["claims"].get(args.require)
        if row is None:
            print(f"theorygate: unknown claim {args.require}", file=sys.stderr)
            return 2
        if not row["supported"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
