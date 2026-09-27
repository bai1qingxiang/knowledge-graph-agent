from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class ExtractedFact:
    source_type: str
    source_name: str
    predicate: str
    target_type: str
    target_name: str
    evidence_quote: str
    confidence: float


class FactExtractor(Protocol):
    def extract(self, text: str) -> list[ExtractedFact]: ...

