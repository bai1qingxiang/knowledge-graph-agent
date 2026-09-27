import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_agent.application import GraphService  # noqa: E402
from kg_agent.application.agent_service import KnowledgeGraphAgent  # noqa: E402
from kg_agent.domain import Entity, Evidence, Relation  # noqa: E402
from kg_agent.infrastructure import SQLiteGraphRepository  # noqa: E402


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SQLiteGraphRepository(Path(self.temp_dir.name) / "test.db")
        self.service = GraphService(self.repository)

    def tearDown(self) -> None:
        self.repository.close()
        self.temp_dir.cleanup()

    def test_path_and_evidence_are_traceable(self) -> None:
        project = self.service.save_entity(Entity(type="Project", name="KG Agent"))
        component = self.service.save_entity(Entity(type="Component", name="API"))
        technology = self.service.save_entity(Entity(type="Technology", name="SQLite"))

        part_of = self.service.save_relation(
            Relation(source_id=component.id, predicate="PART_OF", target_id=project.id)
        )
        uses = self.service.save_relation(
            Relation(source_id=project.id, predicate="USES", target_id=technology.id)
        )
        self.service.attach_evidence(
            uses.id,
            Evidence(document_id="architecture.md", quote="The MVP uses SQLite."),
        )

        paths = self.service.paths(component.id, technology.id, max_depth=2)
        self.assertEqual(len(paths), 1)
        self.assertEqual([step.relation.id for step in paths[0].steps], [part_of.id, uses.id])

        answer = KnowledgeGraphAgent(self.repository).explain_connection(component.id, technology.id)
        self.assertIn("SQLite", answer.answer)
        self.assertEqual(len(answer.evidence), 1)

    def test_rejects_unknown_predicate(self) -> None:
        with self.assertRaises(ValueError):
            self.service.save_relation(Relation(source_id="a", predicate="MADE_UP", target_id="b"))

    def test_rejects_nonaccepted_formal_relation(self) -> None:
        source = self.service.save_entity(Entity(type="Project", name="Source"))
        target = self.service.save_entity(Entity(type="Technology", name="Target"))
        with self.assertRaises(ValueError):
            self.service.save_relation(
                Relation(
                    source_id=source.id,
                    predicate="USES",
                    target_id=target.id,
                    status="rejected",
                )
            )


if __name__ == "__main__":
    unittest.main()
