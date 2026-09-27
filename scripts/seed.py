import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_agent.application import GraphService  # noqa: E402
from kg_agent.domain import Entity, Evidence, Relation  # noqa: E402
from kg_agent.infrastructure import SQLiteGraphRepository  # noqa: E402


def main() -> None:
    source = json.loads((ROOT / "data" / "sample_graph.json").read_text(encoding="utf-8"))
    repository = SQLiteGraphRepository(ROOT / "data" / "knowledge_graph.db")
    service = GraphService(repository)
    entities: dict[str, Entity] = {}

    for item in source["entities"]:
        key = item.pop("key")
        entities[key] = service.save_entity(Entity(**item))

    for item in source["relations"]:
        relation = service.save_relation(
            Relation(
                source_id=entities[item["source"]].id,
                predicate=item["predicate"],
                target_id=entities[item["target"]].id,
                confidence=item.get("confidence", 1.0),
            )
        )
        evidence = item.get("evidence")
        if evidence:
            service.attach_evidence(relation.id, Evidence(**evidence))

    repository.close()
    print("示例图谱已写入 data/knowledge_graph.db")


if __name__ == "__main__":
    main()

