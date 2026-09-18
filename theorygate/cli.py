from __future__ import annotations

import argparse
import json
import sys

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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="theorygate",
        description="Audit evidence-to-claim promotion boundaries.",
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
