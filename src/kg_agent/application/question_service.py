from dataclasses import asdict, dataclass, field

from kg_agent.domain import Evidence
from kg_agent.ports import GraphAnswerer, GraphRepository


@dataclass(slots=True)
class AnswerCitation:
    relation_id: str
    source_name: str
    predicate: str
    target_name: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class GroundedAnswer:
    question: str
    answer: str
    insufficient: bool
    citations: list[AnswerCitation] = field(default_factory=list)


class GraphQuestionService:
    def __init__(self, repository: GraphRepository, answerer: GraphAnswerer) -> None:
        self.repository = repository
        self.answerer = answerer

    def ask(self, question: str, max_relations: int = 100) -> GroundedAnswer:
        question = question.strip()
        if not question:
            raise ValueError("question cannot be blank")

        entities = {entity.id: entity for entity in self.repository.list_entities(2000)}
        fact_by_relation: dict[str, dict] = {}
        evidence_by_id: dict[str, Evidence] = {}
        facts: list[dict] = []

        for relation in self.repository.list_relations(max_relations):
            source = entities.get(relation.source_id)
            target = entities.get(relation.target_id)
            evidence = self.repository.relation_evidence(relation.id)
            if source is None or target is None or not evidence:
                continue
            fact = {
                "relation_id": relation.id,
                "source": {"name": source.name, "type": source.type},
                "predicate": relation.predicate,
                "target": {"name": target.name, "type": target.type},
                "confidence": relation.confidence,
                "evidence": [
                    {
                        "evidence_id": item.id,
                        "document_id": item.document_id,
                        "quote": item.quote[:800],
                        "source_uri": item.source_uri,
                    }
                    for item in evidence
                ],
            }
            facts.append(fact)
            fact_by_relation[relation.id] = fact
            evidence_by_id.update({item.id: item for item in evidence})

        if not facts:
            return GroundedAnswer(
                question=question,
                answer="当前知识图谱中没有带证据的正式关系，暂时无法回答这个问题。",
                insufficient=True,
            )

        draft = self.answerer.answer(question, facts)
        requested_evidence = set(draft.evidence_ids)
        citations: list[AnswerCitation] = []
        for relation_id in dict.fromkeys(draft.relation_ids):
            fact = fact_by_relation.get(relation_id)
            if fact is None:
                continue
            selected = [
                evidence_by_id[item["evidence_id"]]
                for item in fact["evidence"]
                if item["evidence_id"] in requested_evidence
                and item["evidence_id"] in evidence_by_id
            ]
            if selected:
                citations.append(
                    AnswerCitation(
                        relation_id=relation_id,
                        source_name=fact["source"]["name"],
                        predicate=fact["predicate"],
                        target_name=fact["target"]["name"],
                        evidence=selected,
                    )
                )

        insufficient = bool(draft.insufficient or not citations)
        answer = draft.answer.strip()
        if insufficient and not draft.insufficient:
            answer = "现有图谱中没有足够的可验证证据来回答这个问题。"
        if not answer:
            answer = "现有图谱中没有足够的可验证证据来回答这个问题。"
            insufficient = True
        return GroundedAnswer(
            question=question,
            answer=answer,
            insufficient=insufficient,
            citations=citations if not insufficient else [],
        )

    @staticmethod
    def as_dict(answer: GroundedAnswer) -> dict:
        return asdict(answer)
