from kg_agent.domain import Entity, Evidence, Relation
from kg_agent.ports import GraphRepository

from .graph_service import GraphService


class CandidateReviewService:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository
        self.graph = GraphService(repository)

    def list_pending(self, limit: int = 100):
        return self.repository.list_candidates("pending", limit)

    def accept(self, candidate_id: str):
        candidate = self._pending_candidate(candidate_id)
        source = self.graph.save_entity(
            Entity(type=candidate.source_type, name=candidate.source_name)
        )
        target = self.graph.save_entity(
            Entity(type=candidate.target_type, name=candidate.target_name)
        )
        relation = self.graph.save_relation(
            Relation(
                source_id=source.id,
                predicate=candidate.predicate,
                target_id=target.id,
                confidence=candidate.confidence,
                status="accepted",
                metadata={"candidate_id": candidate.id},
            )
        )
        self.graph.attach_evidence(
            relation.id,
            Evidence(
                document_id=candidate.document_id,
                chunk_id=candidate.chunk_id,
                quote=candidate.evidence_quote,
                source_uri=candidate.source_uri,
            ),
        )
        return self.repository.update_candidate_status(candidate.id, "accepted", relation.id)

    def reject(self, candidate_id: str):
        candidate = self._pending_candidate(candidate_id)
        return self.repository.update_candidate_status(candidate.id, "rejected")

    def _pending_candidate(self, candidate_id: str):
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        if candidate.status != "pending":
            raise ValueError(f"Candidate is already {candidate.status}")
        return candidate

