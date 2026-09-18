from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any

from .model import (
    AuditDocument,
    ClaimResult,
    Obligation,
    ObligationResult,
    Requirement,
    Status,
)


def _aggregate(statuses: list[Status], combine: str) -> Status:
    if not statuses:
        return Status.OPEN

    if combine == "any":
        if Status.PASS in statuses:
            return Status.PASS
        if Status.MODEL_CHOICE in statuses:
            return Status.MODEL_CHOICE
        if Status.PARTIAL in statuses:
            return Status.PARTIAL
        if Status.OPEN in statuses:
            return Status.OPEN
        if Status.NOT_APPLICABLE in statuses and all(
            s == Status.NOT_APPLICABLE for s in statuses
        ):
            return Status.NOT_APPLICABLE
        return Status.FAIL

    # all: conservative aggregation
    if Status.FAIL in statuses:
        return Status.FAIL
    if Status.OPEN in statuses:
        return Status.OPEN
    if Status.PARTIAL in statuses:
        return Status.PARTIAL
    if Status.MODEL_CHOICE in statuses:
        return Status.MODEL_CHOICE
    if all(s == Status.NOT_APPLICABLE for s in statuses):
        return Status.NOT_APPLICABLE
    return Status.PASS


def _satisfied(req: Requirement, status: Status) -> bool:
    return status in req.accept


def evaluate_document(doc: AuditDocument) -> dict[str, Any]:
    obligations = {x.id: x for x in doc.obligations}
    evidence_by_obligation = defaultdict(list)
    for ev in doc.evidence:
        evidence_by_obligation[ev.obligation].append(ev)

    cache: dict[str, ObligationResult] = {}

    def eval_obligation(ob: Obligation) -> ObligationResult:
        if ob.id in cache:
            return cache[ob.id]

        blockers: list[str] = []
        for req in ob.depends_on:
            dep = eval_obligation(obligations[req.id])
            if not _satisfied(req, dep.status):
                blockers.append(f"{req.id}={dep.status.value}")
        evs = evidence_by_obligation[ob.id]
        if blockers:
            result = ObligationResult(
                id=ob.id,
                status=Status.BLOCKED,
                evidence_ids=tuple(x.id for x in evs),
                blockers=tuple(blockers),
            )
        else:
            result = ObligationResult(
                id=ob.id,
                status=_aggregate([x.status for x in evs], ob.combine),
                evidence_ids=tuple(x.id for x in evs),
            )
        cache[ob.id] = result
        return result

    obligation_results = {x.id: eval_obligation(x) for x in doc.obligations}

    claim_results: dict[str, ClaimResult] = {}
    for claim in doc.claims:
        blockers: list[str] = []
        caveats: list[str] = []
        for req in claim.requires:
            status = obligation_results[req.id].status
            if not _satisfied(req, status):
                blockers.append(
                    f"{req.id}={status.value} (accept: {','.join(x.value for x in req.accept)})"
                )
            elif status != Status.PASS:
                caveats.append(f"{req.id}={status.value}")
        claim_results[claim.id] = ClaimResult(
            id=claim.id,
            supported=not blockers,
            blockers=tuple(blockers),
            caveats=tuple(caveats),
        )

    supported = [
        claim
        for claim in doc.claims
        if claim_results[claim.id].supported
    ]
    strongest = max(supported, key=lambda x: (x.rank, x.id), default=None)

    return {
        "version": doc.version,
        "model": {
            "id": doc.model.id,
            "title": doc.model.title,
            "choices": doc.model.choices,
        },
        "obligations": {
            oid: {
                "title": obligations[oid].title,
                "kind": obligations[oid].kind,
                "status": result.status.value,
                "evidence": list(result.evidence_ids),
                "blockers": list(result.blockers),
            }
            for oid, result in obligation_results.items()
        },
        "claims": {
            claim.id: {
                "title": claim.title,
                "rank": claim.rank,
                "statement": claim.statement,
                "supported": claim_results[claim.id].supported,
                "blockers": list(claim_results[claim.id].blockers),
                "caveats": list(claim_results[claim.id].caveats),
            }
            for claim in doc.claims
        },
        "strongest_supported_claim": None if strongest is None else strongest.id,
    }
