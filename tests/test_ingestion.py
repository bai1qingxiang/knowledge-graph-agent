import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_agent.application.ingestion_service import DocumentIngestionService, chunk_text  # noqa: E402
from kg_agent.application.review_service import CandidateReviewService  # noqa: E402
from kg_agent.infrastructure import SQLiteGraphRepository  # noqa: E402
from kg_agent.ports import ExtractedFact  # noqa: E402


class StubExtractor:
    def __init__(self, facts: list[ExtractedFact]) -> None:
        self.facts = facts

    def extract(self, text: str) -> list[ExtractedFact]:
        return self.facts


class IngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SQLiteGraphRepository(Path(self.temp_dir.name) / "test.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.temp_dir.cleanup()

    def test_candidate_requires_verbatim_evidence_and_can_be_accepted(self) -> None:
        quote = "知识图谱 Agent 使用 DeepSeek 抽取实体关系。"
        extractor = StubExtractor(
            [
                ExtractedFact(
                    source_type="Project",
                    source_name="知识图谱 Agent",
                    predicate="USES",
                    target_type="Technology",
                    target_name="DeepSeek",
                    evidence_quote=quote,
                    confidence=0.95,
                ),
                ExtractedFact(
                    source_type="Project",
                    source_name="知识图谱 Agent",
                    predicate="USES",
                    target_type="Technology",
                    target_name="不存在的技术",
                    evidence_quote="这句话没有出现在原文中",
                    confidence=0.5,
                ),
            ]
        )
        report = DocumentIngestionService(self.repository, extractor).ingest(
            "design.md", quote, "design.md"
        )

        self.assertEqual(report.candidates_created, 1)
        self.assertEqual(report.facts_skipped, 1)
        candidate = self.repository.get_candidate(report.candidate_ids[0])
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.status, "pending")

        accepted = CandidateReviewService(self.repository).accept(candidate.id)
        self.assertEqual(accepted.status, "accepted")
        self.assertIsNotNone(accepted.relation_id)
        evidence = self.repository.relation_evidence(accepted.relation_id)
        self.assertEqual([item.quote for item in evidence], [quote])

    def test_rejected_candidate_cannot_be_reviewed_twice(self) -> None:
        quote = "项目使用 SQLite。"
        extractor = StubExtractor(
            [
                ExtractedFact(
                    source_type="Project",
                    source_name="项目",
                    predicate="USES",
                    target_type="Technology",
                    target_name="SQLite",
                    evidence_quote=quote,
                    confidence=0.9,
                )
            ]
        )
        report = DocumentIngestionService(self.repository, extractor).ingest("doc-1", quote)
        candidate_id = report.candidate_ids[0]
        review = CandidateReviewService(self.repository)
        review.reject(candidate_id)
        with self.assertRaises(ValueError):
            review.accept(candidate_id)

    def test_chunk_text_keeps_overlap_and_rejects_bad_settings(self) -> None:
        text = "A" * 2000
        chunks = chunk_text(text, max_chars=1000, overlap_chars=100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0][-100:], chunks[1][:100])
        with self.assertRaises(ValueError):
            chunk_text(text, max_chars=400)

    def test_rejects_document_over_budget_before_model_calls(self) -> None:
        extractor = StubExtractor([])
        with self.assertRaises(ValueError):
            DocumentIngestionService(self.repository, extractor).ingest(
                "too-large.txt", "A" * 50_001
            )


if __name__ == "__main__":
    unittest.main()
