from dataclasses import dataclass

from kg_agent.domain import CandidateFact
from kg_agent.ports import FactExtractor, GraphRepository

from .graph_service import GraphService


MAX_DOCUMENT_CHARS = 50_000
MAX_DOCUMENT_CHUNKS = 20
MAX_CANDIDATES_PER_DOCUMENT = 500


@dataclass(slots=True)
class IngestionReport:
    document_id: str
    chunks_processed: int
    candidates_created: int
    facts_skipped: int
    candidate_ids: list[str]


def chunk_text(text: str, max_chars: int = 3500, overlap_chars: int = 300) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    if max_chars < 500:
        raise ValueError("max_chars must be at least 500")
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("overlap_chars must be between 0 and max_chars")

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            paragraph_break = normalized.rfind("\n\n", start, end)
            if paragraph_break > start + max_chars // 2:
                end = paragraph_break
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


class DocumentIngestionService:
    def __init__(self, repository: GraphRepository, extractor: FactExtractor) -> None:
        self.repository = repository
        self.extractor = extractor

    def ingest(
        self,
        document_id: str,
        text: str,
        source_uri: str | None = None,
    ) -> IngestionReport:
        if not document_id.strip():
            raise ValueError("document_id cannot be blank")
        if len(text) > MAX_DOCUMENT_CHARS:
            raise ValueError(f"document text cannot exceed {MAX_DOCUMENT_CHARS} characters")
        chunks = chunk_text(text)
        if len(chunks) > MAX_DOCUMENT_CHUNKS:
            raise ValueError(f"document cannot exceed {MAX_DOCUMENT_CHUNKS} chunks")
        candidate_ids: list[str] = []
        skipped = 0

        for index, chunk in enumerate(chunks):
            facts = self.extractor.extract(chunk)
            for fact_index, fact in enumerate(facts):
                if len(candidate_ids) >= MAX_CANDIDATES_PER_DOCUMENT:
                    skipped += len(facts) - fact_index
                    break
                if (
                    fact.source_type not in GraphService.ALLOWED_ENTITY_TYPES
                    or fact.target_type not in GraphService.ALLOWED_ENTITY_TYPES
                    or fact.predicate not in GraphService.ALLOWED_PREDICATES
                    or not 0 <= fact.confidence <= 1
                    or not fact.source_name.strip()
                    or not fact.target_name.strip()
                    or not fact.evidence_quote.strip()
                    or fact.evidence_quote not in chunk
                ):
                    skipped += 1
                    continue

                candidate = self.repository.add_candidate(
                    CandidateFact(
                        document_id=document_id,
                        source_type=fact.source_type,
                        source_name=fact.source_name.strip(),
                        predicate=fact.predicate,
                        target_type=fact.target_type,
                        target_name=fact.target_name.strip(),
                        evidence_quote=fact.evidence_quote.strip(),
                        confidence=fact.confidence,
                        source_uri=source_uri,
                        chunk_id=f"{document_id}#chunk-{index + 1}",
                    )
                )
                if candidate.id not in candidate_ids:
                    candidate_ids.append(candidate.id)

        return IngestionReport(
            document_id=document_id,
            chunks_processed=len(chunks),
            candidates_created=len(candidate_ids),
            facts_skipped=skipped,
            candidate_ids=candidate_ids,
        )
