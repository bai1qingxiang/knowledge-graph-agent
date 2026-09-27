import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from kg_agent.api.app import create_app  # noqa: E402
from kg_agent.ports import AnswerDraft, ExtractedFact  # noqa: E402


class StubExtractor:
    def extract(self, text: str) -> list[ExtractedFact]:
        quote = "项目使用 DeepSeek。"
        return [
            ExtractedFact(
                source_type="Project",
                source_name="项目",
                predicate="USES",
                target_type="Technology",
                target_name="DeepSeek",
                evidence_quote=quote,
                confidence=0.96,
            )
        ]


class StubAnswerer:
    def answer(self, question: str, facts: list[dict]) -> AnswerDraft:
        if "不存在" in question:
            return AnswerDraft(
                answer="这是没有依据的回答",
                relation_ids=["invented-relation"],
                evidence_ids=["invented-evidence"],
            )
        fact = facts[0]
        return AnswerDraft(
            answer="项目使用 DeepSeek。",
            relation_ids=[fact["relation_id"]],
            evidence_ids=[fact["evidence"][0]["evidence_id"]],
        )


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        app = create_app(
            Path(self.temp_dir.name) / "api.db",
            extractor=StubExtractor(),
            answerer=StubAnswerer(),
        )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_question_without_verified_facts_is_insufficient(self) -> None:
        response = self.client.post(
            "/questions/ask", json={"question": "这个项目使用了什么技术？"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["insufficient"])
        self.assertEqual(response.json()["citations"], [])

    def test_rejects_oversized_documents_and_nonaccepted_relations(self) -> None:
        oversized = self.client.post(
            "/documents/ingest",
            json={"document_id": "too-large", "text": "A" * 50_001},
        )
        self.assertEqual(oversized.status_code, 422)

        invalid_status = self.client.post(
            "/relations",
            json={
                "source_id": "source",
                "predicate": "USES",
                "target_id": "target",
                "status": "pending",
            },
        )
        self.assertEqual(invalid_status.status_code, 422)

    def test_ingest_review_and_query_flow(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("知识图谱 Agent", dashboard.text)
        response = self.client.post(
            "/documents/ingest",
            json={
                "document_id": "demo.md",
                "source_uri": "demo.md",
                "text": "项目使用 DeepSeek。",
            },
        )
        self.assertEqual(response.status_code, 200)
        candidate_id = response.json()["candidate_ids"][0]

        pending = self.client.get("/candidates", params={"status": "pending"}).json()
        self.assertEqual([item["id"] for item in pending], [candidate_id])

        accepted = self.client.post(f"/candidates/{candidate_id}/accept")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "accepted")

        entities = self.client.get("/entities/search", params={"q": "DeepSeek"}).json()
        self.assertEqual(entities[0]["name"], "DeepSeek")

        stats = self.client.get("/stats").json()
        self.assertEqual(stats["entities"], 2)
        self.assertEqual(stats["relations"], 1)
        self.assertEqual(stats["evidence"], 1)
        self.assertEqual(stats["candidates_accepted"], 1)

        graph = self.client.get("/graph").json()
        self.assertEqual(len(graph["entities"]), 2)
        self.assertEqual(len(graph["relations"]), 1)
        self.assertEqual(graph["relations"][0]["source_name"], "项目")
        self.assertEqual(graph["relations"][0]["target_name"], "DeepSeek")
        self.assertEqual(graph["relations"][0]["evidence"][0]["quote"], "项目使用 DeepSeek。")

        answer = self.client.post(
            "/questions/ask", json={"question": "项目使用了什么技术？"}
        )
        self.assertEqual(answer.status_code, 200)
        self.assertFalse(answer.json()["insufficient"])
        self.assertEqual(answer.json()["answer"], "项目使用 DeepSeek。")
        self.assertEqual(answer.json()["citations"][0]["predicate"], "USES")
        self.assertEqual(
            answer.json()["citations"][0]["evidence"][0]["quote"],
            "项目使用 DeepSeek。",
        )

        ungrounded = self.client.post(
            "/questions/ask", json={"question": "不存在的事实是什么？"}
        ).json()
        self.assertTrue(ungrounded["insufficient"])
        self.assertEqual(ungrounded["citations"], [])
        self.assertNotIn("没有依据的回答", ungrounded["answer"])


if __name__ == "__main__":
    unittest.main()
