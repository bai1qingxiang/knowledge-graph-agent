from typing import Any, Literal

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationCreate(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    predicate: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=128)
    confidence: float = Field(default=1.0, ge=0, le=1)
    status: Literal["accepted"] = "accepted"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceCreate(BaseModel):
    relation_id: str = Field(min_length=1, max_length=128)
    document_id: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=10_000)
    source_uri: str | None = Field(default=None, max_length=2_048)
    chunk_id: str | None = Field(default=None, max_length=256)
    content_hash: str | None = Field(default=None, max_length=256)


class DocumentIngestRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=50_000)
    source_uri: str | None = Field(default=None, max_length=2_048)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
