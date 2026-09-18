from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

    evidence = []
    for item in raw.get("evidence", []):
        if not isinstance(item, dict):
            raise DocumentError(f"invalid evidence: {item!r}")
        for key in ("id", "obligation", "status", "engine"):
            if key not in item:
                raise DocumentError(f"evidence missing {key}: {item!r}")
        st = _status(item["status"])
        if st not in EVIDENCE_STATUSES:
            raise DocumentError("evidence cannot have computed status BLOCKED")
        evidence.append(
            Evidence(
                id=str(item["id"]),
                obligation=str(item["obligation"]),
                status=st,
                engine=str(item["engine"]),
                artifact=(None if item.get("artifact") is None else str(item["artifact"])),
                note=str(item.get("note", "")),
                metadata=dict(item.get("metadata", {})),
            )
        )

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
        evidence=tuple(evidence),
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

    # cycle check
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
    text = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()
    if suffix == ".json":
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    else:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            raw = yaml.safe_load(text)
    return parse_document(raw)
