from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, Iterable

import yaml

from .model import (
    AuditDocument,
    Claim,
    Evidence,
    EVIDENCE_STATUSES,
    ModelSpec,
    Obligation,
    Requirement,
    Status,
)


class DocumentError(ValueError):
    pass


def _status(value: str) -> Status:
    try:
        return Status(str(value).upper())
    except ValueError as exc:
        raise DocumentError(f"unknown status: {value!r}") from exc


def _requirement(raw: Any) -> Requirement:
    if isinstance(raw, str):
        return Requirement(id=raw)
    if not isinstance(raw, dict) or "id" not in raw:
        raise DocumentError(f"invalid requirement: {raw!r}")
    accepted = raw.get("accept", ["PASS"])
    if isinstance(accepted, str):
        accepted = [accepted]
    values = tuple(_status(x) for x in accepted)
    if Status.BLOCKED in values:
        raise DocumentError("BLOCKED cannot be an accepted source status")
    return Requirement(id=str(raw["id"]), accept=values)


def _evidence_item(raw: Any, *, source: str | None = None) -> Evidence:
    if not isinstance(raw, dict):
        raise DocumentError(f"invalid evidence: {raw!r}")
    for key in ("id", "obligation", "status", "engine"):
        if key not in raw:
            where = f" in {source}" if source else ""
            raise DocumentError(f"evidence missing {key}{where}: {raw!r}")
    st = _status(raw["status"])
    if st not in EVIDENCE_STATUSES:
        raise DocumentError("evidence cannot have computed status BLOCKED")
    metadata = dict(raw.get("metadata", {}))
    if source is not None:
        metadata.setdefault("theorygate_ingested_from", source)
    return Evidence(
        id=str(raw["id"]),
        obligation=str(raw["obligation"]),
        status=st,
        engine=str(raw["engine"]),
        artifact=(None if raw.get("artifact") is None else str(raw["artifact"])),
        note=str(raw.get("note", "")),
        metadata=metadata,
    )


def parse_evidence_payload(raw: Any, *, source: str = "<external>") -> tuple[Evidence, ...]:
    """Parse external evidence in one of three shapes.

    Accepted forms:

    1. one evidence object;
    2. a list of evidence objects;
    3. a bundle object with an `evidence` field containing either form.

    The source path is recorded in evidence metadata for ingestion provenance.
    """
    payload = raw
    if isinstance(raw, dict) and "evidence" in raw and not all(
        key in raw for key in ("id", "obligation", "status", "engine")
    ):
        payload = raw["evidence"]

    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        raise DocumentError(
            f"external evidence {source} must be an evidence object, list, "
            "or bundle with an evidence field"
        )

    return tuple(_evidence_item(item, source=source) for item in items)


def _load_serialized(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def parse_document(raw: dict[str, Any]) -> AuditDocument:
    if not isinstance(raw, dict):
        raise DocumentError("document root must be an object")

    version = str(raw.get("version", "0.1"))
    model_raw = raw.get("model")
    if not isinstance(model_raw, dict) or "id" not in model_raw:
        raise DocumentError("model.id is required")
    model = ModelSpec(
        id=str(model_raw["id"]),
        title=str(model_raw.get("title", model_raw["id"])),
        choices=dict(model_raw.get("choices", {})),
    )

    obligations = []
    for item in raw.get("obligations", []):
        if not isinstance(item, dict) or "id" not in item:
            raise DocumentError(f"invalid obligation: {item!r}")
        combine = str(item.get("combine", "all")).lower()
        if combine not in {"all", "any"}:
            raise DocumentError(f"obligation {item['id']}: combine must be all or any")
        obligations.append(
            Obligation(
                id=str(item["id"]),
                title=str(item.get("title", item["id"])),
                kind=str(item.get("kind", "unspecified")),
                depends_on=tuple(_requirement(x) for x in item.get("depends_on", [])),
                combine=combine,
                description=str(item.get("description", "")),
            )
        )

    evidence = tuple(_evidence_item(item) for item in raw.get("evidence", []))

    claims = []
    for item in raw.get("claims", []):
        if not isinstance(item, dict) or "id" not in item:
            raise DocumentError(f"invalid claim: {item!r}")
        claims.append(
            Claim(
                id=str(item["id"]),
                title=str(item.get("title", item["id"])),
                rank=int(item.get("rank", 0)),
                statement=str(item.get("statement", "")),
                requires=tuple(_requirement(x) for x in item.get("requires", [])),
            )
        )

    doc = AuditDocument(
        version=version,
        model=model,
        obligations=tuple(obligations),
        evidence=evidence,
        claims=tuple(claims),
    )
    validate_document(doc)
    return doc


def validate_document(doc: AuditDocument) -> None:
    def unique(kind: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise DocumentError(f"duplicate {kind} id")

    obligation_ids = [x.id for x in doc.obligations]
    evidence_ids = [x.id for x in doc.evidence]
    claim_ids = [x.id for x in doc.claims]
    unique("obligation", obligation_ids)
    unique("evidence", evidence_ids)
    unique("claim", claim_ids)

    known = set(obligation_ids)
    for ob in doc.obligations:
        for dep in ob.depends_on:
            if dep.id not in known:
                raise DocumentError(f"obligation {ob.id} depends on unknown obligation {dep.id}")
    for ev in doc.evidence:
        if ev.obligation not in known:
            raise DocumentError(f"evidence {ev.id} targets unknown obligation {ev.obligation}")
    for claim in doc.claims:
        for req in claim.requires:
            if req.id not in known:
                raise DocumentError(f"claim {claim.id} requires unknown obligation {req.id}")

    graph = {x.id: [r.id for r in x.depends_on] for x in doc.obligations}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise DocumentError(f"obligation dependency cycle includes {node}")
        visiting.add(node)
        for child in graph[node]:
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def load_document(path: str | Path) -> AuditDocument:
    p = Path(path)
    return parse_document(_load_serialized(p))


def load_evidence_patterns(patterns: Iterable[str]) -> tuple[Evidence, ...]:
    """Load external evidence from exact paths and/or glob patterns.

    Patterns are expanded by TheoryGate, so callers may quote shell globs:

        --evidence 'artifacts/*.json'

    Overlapping patterns that resolve to the same file are de-duplicated by
    resolved path. A pattern matching no files is an error rather than a silent
    no-op.
    """
    paths: list[Path] = []
    seen: set[Path] = set()

    for pattern in patterns:
        matches = sorted(glob.glob(pattern, recursive=True))
        if not matches:
            raise DocumentError(f"evidence pattern matched no files: {pattern}")
        for match in matches:
            p = Path(match)
            if not p.is_file():
                continue
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                paths.append(p)

    if not paths:
        raise DocumentError("no evidence files were resolved")

    evidence: list[Evidence] = []
    for path in paths:
        raw = _load_serialized(path)
        evidence.extend(parse_evidence_payload(raw, source=str(path)))
    return tuple(evidence)


def merge_evidence(
    doc: AuditDocument,
    external: Iterable[Evidence],
    *,
    replace_existing: bool = False,
) -> AuditDocument:
    """Merge external evidence into an audit document.

    Duplicate evidence IDs are rejected by default. With `replace_existing`,
    later external records explicitly replace earlier records with the same ID,
    including evidence embedded in the model document.

    Unknown obligation targets are always rejected by final document validation.
    """
    merged = list(doc.evidence)
    index = {ev.id: i for i, ev in enumerate(merged)}

    for ev in external:
        if ev.id in index:
            if not replace_existing:
                raise DocumentError(
                    f"duplicate evidence id during ingestion: {ev.id}; "
                    "use --replace-evidence to replace explicitly"
                )
            merged[index[ev.id]] = ev
        else:
            index[ev.id] = len(merged)
            merged.append(ev)

    out = AuditDocument(
        version=doc.version,
        model=doc.model,
        obligations=doc.obligations,
        evidence=tuple(merged),
        claims=doc.claims,
    )
    validate_document(out)
    return out
