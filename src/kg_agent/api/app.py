import json
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kg_agent.application import GraphQuestionService, GraphService
from kg_agent.application.ingestion_service import DocumentIngestionService
from kg_agent.application.review_service import CandidateReviewService
from kg_agent.domain import Entity, Evidence, Relation
from kg_agent.infrastructure import SQLiteGraphRepository
from kg_agent.infrastructure.deepseek_extractor import DeepSeekFactExtractor, UnavailableFactExtractor
from kg_agent.infrastructure.deepseek_answerer import DeepSeekGraphAnswerer, UnavailableGraphAnswerer
from kg_agent.ports import FactExtractor, GraphAnswerer

from .schemas import DocumentIngestRequest, EntityCreate, EvidenceCreate, QuestionRequest, RelationCreate


def create_app(
    database_path: str | Path | None = None,
    extractor: FactExtractor | None = None,
    answerer: GraphAnswerer | None = None,
) -> FastAPI:
    project_root = Path(__file__).resolve().parents[3]
    db_path = database_path or os.getenv(
        "KG_DATABASE_PATH",
        str(project_root / "data" / "knowledge_graph.db"),
    )
    repository = SQLiteGraphRepository(db_path)
    service = GraphService(repository)
    configured_extractor = extractor
    if configured_extractor is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        configured_extractor = (
            DeepSeekFactExtractor(
                api_key=api_key,
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            )
            if api_key
            else UnavailableFactExtractor()
        )
    ingestion = DocumentIngestionService(repository, configured_extractor)
    review = CandidateReviewService(repository)
    configured_answerer = answerer
    if configured_answerer is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        configured_answerer = (
            DeepSeekGraphAnswerer(
                api_key=api_key,
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            )
            if api_key
            else UnavailableGraphAnswerer()
        )
    questions = GraphQuestionService(repository, configured_answerer)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            repository.close()

    api = FastAPI(title="知识图谱 Agent API", version="0.4.0", lifespan=lifespan)
    api.state.repository = repository
    web_dir = project_root / "web"
    api.mount("/static", StaticFiles(directory=web_dir), name="static")

    @api.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/stats")
    def get_stats() -> dict[str, int]:
        return repository.stats()

    @api.get("/graph")
    def get_graph(limit: int = Query(default=500, ge=1, le=2000)) -> dict:
        entities = repository.list_entities(limit)
        entity_names = {entity.id: entity.name for entity in entities}
        relations = []
        for relation in repository.list_relations(limit):
            if relation.source_id not in entity_names or relation.target_id not in entity_names:
                continue
            item = asdict(relation)
            item["source_name"] = entity_names[relation.source_id]
            item["target_name"] = entity_names[relation.target_id]
            item["evidence"] = [asdict(value) for value in repository.relation_evidence(relation.id)]
            relations.append(item)
        return {"entities": [asdict(entity) for entity in entities], "relations": relations}

    @api.post("/questions/ask")
    def ask_question(payload: QuestionRequest) -> dict:
        try:
            return asdict(questions.ask(payload.question))
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"DeepSeek API returned HTTP {exc.response.status_code}",
            ) from exc
        except (RuntimeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/entities")
    def create_entity(payload: EntityCreate) -> dict:
        try:
            return asdict(service.save_entity(Entity(**payload.model_dump())))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/entities/search")
    def search_entities(q: str = Query(min_length=1)) -> list[dict]:
        return [asdict(entity) for entity in service.search(q)]

    @api.post("/relations")
    def create_relation(payload: RelationCreate) -> dict:
        try:
            return asdict(service.save_relation(Relation(**payload.model_dump())))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/evidence")
    def create_evidence(payload: EvidenceCreate) -> dict:
        values = payload.model_dump()
        relation_id = values.pop("relation_id")
        try:
            return asdict(service.attach_evidence(relation_id, Evidence(**values)))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/entities/{entity_id}/neighbors")
    def get_neighbors(entity_id: str, predicate: str | None = None) -> list[dict]:
        return [asdict(relation) for relation in repository.neighbors(entity_id, predicate)]

    @api.get("/paths")
    def get_paths(source_id: str, target_id: str, max_depth: int = Query(default=3, ge=1, le=5)) -> list[dict]:
        try:
            return [asdict(path) for path in service.paths(source_id, target_id, max_depth)]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/documents/ingest")
    def ingest_document(payload: DocumentIngestRequest) -> dict:
        try:
            return asdict(
                ingestion.ingest(
                    document_id=payload.document_id,
                    text=payload.text,
                    source_uri=payload.source_uri,
                )
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise HTTPException(status_code=502, detail=f"DeepSeek API returned HTTP {status}") from exc
        except (RuntimeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/candidates")
    def list_candidates(
        status: str = Query(default="pending", pattern="^(pending|accepted|rejected)$"),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict]:
        return [asdict(item) for item in repository.list_candidates(status, limit)]

    @api.post("/candidates/{candidate_id}/accept")
    def accept_candidate(candidate_id: str) -> dict:
        try:
            return asdict(review.accept(candidate_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Candidate not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/candidates/{candidate_id}/reject")
    def reject_candidate(candidate_id: str) -> dict:
        try:
            return asdict(review.reject(candidate_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Candidate not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return api


app = create_app()
