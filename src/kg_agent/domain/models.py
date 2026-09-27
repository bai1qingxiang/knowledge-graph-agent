from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Entity:
    type: str
    name: str
    id: str = field(default_factory=new_id)
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Relation:
    source_id: str
    predicate: str
    target_id: str
    confidence: float = 1.0
    status: str = "accepted"
    id: str = field(default_factory=new_id)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class Evidence:
    document_id: str
    quote: str
    source_uri: str | None = None
    chunk_id: str | None = None
    content_hash: str | None = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class PathStep:
    relation: Relation
    source: Entity
    target: Entity


@dataclass(slots=True)
class GraphPath:
    steps: list[PathStep]


@dataclass(slots=True)
class CandidateFact:
    document_id: str
    source_type: str
    source_name: str
    predicate: str
    target_type: str
    target_name: str
    evidence_quote: str
    confidence: float
    source_uri: str | None = None
    chunk_id: str | None = None
    status: str = "pending"
    relation_id: str | None = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=utc_now)
    reviewed_at: str | None = None
