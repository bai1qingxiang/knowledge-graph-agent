from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class AnswerDraft:
    answer: str
    relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    insufficient: bool = False


class GraphAnswerer(Protocol):
    def answer(self, question: str, facts: list[dict[str, Any]]) -> AnswerDraft: ...
