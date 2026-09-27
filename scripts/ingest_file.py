import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kg_agent.application.ingestion_service import DocumentIngestionService  # noqa: E402
from kg_agent.infrastructure import SQLiteGraphRepository  # noqa: E402
from kg_agent.infrastructure.deepseek_extractor import DeepSeekFactExtractor  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/ingest_file.py <Markdown 或 TXT 文件>")

    source = Path(sys.argv[1]).resolve()
    if source.suffix.lower() not in {".md", ".txt"}:
        raise SystemExit("当前只支持 .md 和 .txt 文件")
    if not source.is_file():
        raise SystemExit(f"文件不存在：{source}")

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise SystemExit("请先设置 DEEPSEEK_API_KEY 环境变量")

    repository = SQLiteGraphRepository(
        os.getenv("KG_DATABASE_PATH", str(ROOT / "data" / "knowledge_graph.db"))
    )
    extractor = DeepSeekFactExtractor(
        api_key=api_key,
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
    )
    try:
        report = DocumentIngestionService(repository, extractor).ingest(
            document_id=source.name,
            text=source.read_text(encoding="utf-8"),
            source_uri=str(source),
        )
    finally:
        repository.close()

    print(f"处理分块：{report.chunks_processed}")
    print(f"新增候选：{report.candidates_created}")
    print(f"跳过事实：{report.facts_skipped}")
    for candidate_id in report.candidate_ids:
        print(f"- {candidate_id}")


if __name__ == "__main__":
    main()

