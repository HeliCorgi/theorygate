from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

from .adapters.cas import (
    ExternalCASConfig,
    collect_external_cas_evidence,
    collect_sympy_evidence,
    write_evidence_json as write_cas_evidence_json,
)
from .adapters.lean import LeanEvidenceConfig, collect_lean_evidence, write_evidence_json
from .adapters.robustness import (
    collect_robustness_evidence,
    write_evidence_json as write_robustness_evidence_json,
)
from .evaluate import evaluate_document
from .io import (
    DocumentError,
    load_document,
    load_evidence_patterns,
    merge_evidence,
)
from .templates.physics import TEMPLATE_NAMES, get_template, render_template_document


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


def _common_output_args(parser) -> None:
    parser.add_argument("--id", required=True, dest="evidence_id", help="evidence id")
    parser.add_argument("--obligation", required=True, help="target TheoryGate obligation id")
    parser.add_argument("--artifact", help="override evidence artifact/provenance string")
    parser.add_argument("--output", help="write evidence JSON to this path instead of stdout")
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="exit 1 unless generated evidence status is PASS",
    )


def _add_evidence_parsers(sub) -> None:
    evidence = sub.add_parser(
        "evidence",
        help="collect evidence from formal, symbolic, or robustness engines",
    )
    engines = evidence.add_subparsers(dest="evidence_engine", required=True)

    lean = engines.add_parser(
        "lean",
        help="run lake build and #print axioms, then emit TheoryGate evidence",
    )
    lean.add_argument("--project", required=True, help="Lean/Lake project directory")
    _common_output_args(lean)
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
        "--timeout",
        type=float,
        default=600.0,
        help="per-command timeout in seconds (default: 600)",
    )

    cas = engines.add_parser("cas", help="collect symbolic CAS evidence")
    cas_engines = cas.add_subparsers(dest="cas_engine", required=True)

    sympy_p = cas_engines.add_parser(
        "sympy",
        help="evaluate symbolic identities from a JSON/YAML spec with SymPy",
    )
    sympy_p.add_argument("--spec", required=True, help="symbolic check specification")
    _common_output_args(sympy_p)

    for engine in ("xact", "cadabra"):
        p = cas_engines.add_parser(
            engine,
            help=f"run a {engine} audit script under the TheoryGate marker contract",
        )
        p.add_argument("--script", required=True, help="audit script path")
        _common_output_args(p)
        p.add_argument("--executable", help="override wolframscript/cadabra2 executable")
        p.add_argument("--pass-marker", default="THEORYGATE:PASS")
        p.add_argument("--fail-marker", default="THEORYGATE:FAIL")
        p.add_argument("--timeout", type=float, default=600.0)

    robust = engines.add_parser(
        "robustness",
        help="evaluate regulator/clock/ordering/boundary robustness scan",
    )
    robust.add_argument("--spec", required=True, help="robustness scan JSON/YAML")
    _common_output_args(robust)


def _add_template_parser(sub) -> None:
    template = sub.add_parser(
        "template",
        help="inspect or initialize conservative physical claim templates",
    )
    actions = template.add_subparsers(dest="template_action", required=True)

    actions.add_parser("list", help="list built-in physical claim templates")

    show = actions.add_parser("show", help="show one template")
    show.add_argument("name", choices=TEMPLATE_NAMES)

    init = actions.add_parser("init", help="write a model skeleton from one template")
    init.add_argument("name", choices=TEMPLATE_NAMES)
    init.add_argument("--model-id", required=True)
    init.add_argument("--title")
    init.add_argument("--output", required=True)


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
        "--evidence",
        action="append",
        default=[],
        metavar="PATH_OR_GLOB",
        help=(
            "ingest external evidence JSON/YAML before evaluation; repeatable. "
            "Globs are expanded by TheoryGate, e.g. --evidence 'artifacts/*.json'"
        ),
    )
    check.add_argument(
        "--replace-evidence",
        action="store_true",
        help="explicitly allow ingested evidence to replace an existing evidence id",
    )
    check.add_argument(
        "--require",
        metavar="CLAIM_ID",
        help="exit non-zero unless this claim is supported",
    )

    validate = sub.add_parser("validate", help="validate an audit document")
    validate.add_argument("path")

    _add_evidence_parsers(sub)
    _add_template_parser(sub)
    return p


def _emit_evidence(evidence: dict, output: str | None, writer, require_pass: bool) -> int:
    if output:
        writer(evidence, output)
        print(f"{evidence['status']}: wrote {output}")
    else:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    if require_pass and evidence["status"] != "PASS":
        return 1
    return 0


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
    return _emit_evidence(
        evidence, args.output, write_evidence_json, bool(args.require_pass)
    )


def _run_cas_evidence(args) -> int:
    if args.cas_engine == "sympy":
        evidence = collect_sympy_evidence(
            spec_path=args.spec,
            evidence_id=args.evidence_id,
            obligation=args.obligation,
            artifact=args.artifact,
        )
    else:
        evidence = collect_external_cas_evidence(
            ExternalCASConfig(
                engine=args.cas_engine,
                script=Path(args.script),
                evidence_id=args.evidence_id,
                obligation=args.obligation,
                executable=args.executable,
                pass_marker=args.pass_marker,
                fail_marker=args.fail_marker,
                timeout=float(args.timeout),
                artifact=args.artifact,
            )
        )
    return _emit_evidence(
        evidence, args.output, write_cas_evidence_json, bool(args.require_pass)
    )


def _run_robustness_evidence(args) -> int:
    evidence = collect_robustness_evidence(
        spec_path=args.spec,
        evidence_id=args.evidence_id,
        obligation=args.obligation,
        artifact=args.artifact,
    )
    return _emit_evidence(
        evidence,
        args.output,
        write_robustness_evidence_json,
        bool(args.require_pass),
    )


def _run_template(args) -> int:
    if args.template_action == "list":
        for name in TEMPLATE_NAMES:
            print(name)
        return 0
    if args.template_action == "show":
        print(yaml.safe_dump(get_template(args.name), sort_keys=False))
        return 0
    doc = render_template_document(
        args.name,
        model_id=args.model_id,
        title=args.title,
    )
    path = Path(args.output)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    print(f"wrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "evidence":
        if args.evidence_engine == "lean":
            return _run_lean_evidence(args)
        if args.evidence_engine == "cas":
            return _run_cas_evidence(args)
        if args.evidence_engine == "robustness":
            return _run_robustness_evidence(args)
        return 2

    if args.command == "template":
        return _run_template(args)

    try:
        doc = load_document(args.path)
        if args.command == "check" and args.evidence:
            external = load_evidence_patterns(args.evidence)
            doc = merge_evidence(
                doc,
                external,
                replace_existing=bool(args.replace_evidence),
            )
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
