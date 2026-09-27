from dataclasses import dataclass

from kg_agent.domain import Evidence, GraphPath
from kg_agent.ports import GraphRepository


@dataclass(slots=True)
class TraceableAnswer:
    answer: str
    paths: list[GraphPath]
    evidence: list[Evidence]


class KnowledgeGraphAgent:
    """Minimal deterministic agent; replace answer composition with an LLM later."""

    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

    def explain_connection(self, source_id: str, target_id: str, max_depth: int = 3) -> TraceableAnswer:
        paths = self.repository.find_paths(source_id, target_id, max_depth=max_depth)
        evidence_by_id: dict[str, Evidence] = {}
        for path in paths:
            for step in path.steps:
                for evidence in self.repository.relation_evidence(step.relation.id):
                    evidence_by_id[evidence.id] = evidence

        if not paths:
            return TraceableAnswer("没有找到可验证的关系路径。", [], [])

        first = paths[0]
        summary = " → ".join(
            [first.steps[0].source.name]
            + [f"{step.relation.predicate} → {step.target.name}" for step in first.steps]
        )
        return TraceableAnswer(summary, paths, list(evidence_by_id.values()))

