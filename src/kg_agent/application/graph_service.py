from kg_agent.domain import Entity, Evidence, GraphPath, Relation
from kg_agent.ports import GraphRepository


class GraphService:
    """Application boundary used by HTTP, OpenClaw tools, and future jobs."""

    ALLOWED_ENTITY_TYPES = {"Person", "Project", "Component", "Technology", "Decision", "Document"}
    ALLOWED_PREDICATES = {
        "OWNS",
        "PART_OF",
        "DEPENDS_ON",
        "USES",
        "DECIDED_BY",
        "AFFECTS",
        "DOCUMENTED_IN",
    }

    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

    def save_entity(self, entity: Entity) -> Entity:
        if entity.type not in self.ALLOWED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity type: {entity.type}")
        if not entity.name.strip():
            raise ValueError("Entity name cannot be blank")
        return self.repository.upsert_entity(entity)

    def save_relation(self, relation: Relation) -> Relation:
        if relation.predicate not in self.ALLOWED_PREDICATES:
            raise ValueError(f"Unsupported predicate: {relation.predicate}")
        if not 0 <= relation.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        if relation.status != "accepted":
            raise ValueError("Formal relations must have accepted status")
        return self.repository.add_relation(relation)

    def attach_evidence(self, relation_id: str, evidence: Evidence) -> Evidence:
        if not evidence.quote.strip():
            raise ValueError("Evidence quote cannot be blank")
        return self.repository.add_evidence(evidence, relation_id)

    def search(self, query: str) -> list[Entity]:
        return self.repository.search_entities(query.strip())

    def paths(self, source_id: str, target_id: str, max_depth: int = 3) -> list[GraphPath]:
        return self.repository.find_paths(source_id, target_id, max_depth)
