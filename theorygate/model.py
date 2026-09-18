from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    OPEN = "OPEN"
    MODEL_CHOICE = "MODEL_CHOICE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


EVIDENCE_STATUSES = {
    Status.PASS,
    Status.FAIL,
    Status.PARTIAL,
    Status.OPEN,
    Status.MODEL_CHOICE,
    Status.NOT_APPLICABLE,
}


@dataclass(frozen=True)
class Requirement:
    id: str
    accept: tuple[Status, ...] = (Status.PASS,)


@dataclass(frozen=True)
class Obligation:
    id: str
    title: str
    kind: str = "unspecified"
    depends_on: tuple[Requirement, ...] = ()
    combine: str = "all"
    description: str = ""


@dataclass(frozen=True)
class Evidence:
    id: str
    obligation: str
    status: Status
    engine: str
    artifact: str | None = None
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Claim:
    id: str
    title: str
    rank: int
    statement: str
    requires: tuple[Requirement, ...] = ()


@dataclass(frozen=True)
class ModelSpec:
    id: str
    title: str
    choices: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditDocument:
    version: str
    model: ModelSpec
    obligations: tuple[Obligation, ...]
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class ObligationResult:
    id: str
    status: Status
    evidence_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimResult:
    id: str
    supported: bool
    blockers: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
