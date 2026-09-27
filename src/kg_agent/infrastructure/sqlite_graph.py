import json
import sqlite3
from collections import deque
from pathlib import Path

from kg_agent.domain import CandidateFact, Entity, Evidence, GraphPath, PathStep, Relation
from kg_agent.domain.models import utc_now


class SQLiteGraphRepository:
    """Small local graph store. Replace this adapter with Neo4j later."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        self._connection.close()

    def _init_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                description TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_type_name
                ON entities(type, name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES entities(id),
                predicate TEXT NOT NULL,
                target_id TEXT NOT NULL REFERENCES entities(id),
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS ix_relations_target ON relations(target_id);

            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_id TEXT,
                quote TEXT NOT NULL,
                source_uri TEXT,
                content_hash TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relation_evidence (
                relation_id TEXT NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
                PRIMARY KEY (relation_id, evidence_id)
            );

            CREATE TABLE IF NOT EXISTS candidate_facts (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                predicate TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_name TEXT NOT NULL,
                evidence_quote TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                source_uri TEXT,
                chunk_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                relation_id TEXT REFERENCES relations(id),
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                UNIQUE(document_id, source_name, predicate, target_name, evidence_quote)
            );
            CREATE INDEX IF NOT EXISTS ix_candidate_facts_status
                ON candidate_facts(status, created_at);
            """
        )
        self._connection.commit()

    def upsert_entity(self, entity: Entity) -> Entity:
        existing = self._connection.execute(
            "SELECT id FROM entities WHERE type = ? AND name = ? COLLATE NOCASE",
            (entity.type, entity.name),
        ).fetchone()
        if existing:
            entity.id = existing["id"]
        self._connection.execute(
            """
            INSERT INTO entities(id, type, name, aliases_json, description, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                name=excluded.name,
                aliases_json=excluded.aliases_json,
                description=excluded.description,
                metadata_json=excluded.metadata_json
            """,
            (
                entity.id,
                entity.type,
                entity.name,
                json.dumps(entity.aliases, ensure_ascii=False),
                entity.description,
                json.dumps(entity.metadata, ensure_ascii=False),
                entity.created_at,
            ),
        )
        self._connection.commit()
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        row = self._connection.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        return self._row_to_entity(row) if row else None

    def search_entities(self, query: str, limit: int = 20) -> list[Entity]:
        pattern = f"%{query}%"
        rows = self._connection.execute(
            """
            SELECT * FROM entities
            WHERE name LIKE ? COLLATE NOCASE OR aliases_json LIKE ? COLLATE NOCASE
            ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 ELSE 1 END, name
            LIMIT ?
            """,
            (pattern, pattern, query, limit),
        ).fetchall()
        return [self._row_to_entity(row) for row in rows]

    def list_entities(self, limit: int = 500) -> list[Entity]:
        rows = self._connection.execute(
            "SELECT * FROM entities ORDER BY created_at ASC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_entity(row) for row in rows]

    def add_relation(self, relation: Relation) -> Relation:
        if not self.get_entity(relation.source_id) or not self.get_entity(relation.target_id):
            raise ValueError("Both source and target entities must exist")
        self._connection.execute(
            """
            INSERT INTO relations(id, source_id, predicate, target_id, confidence, status, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation.id,
                relation.source_id,
                relation.predicate,
                relation.target_id,
                relation.confidence,
                relation.status,
                json.dumps(relation.metadata, ensure_ascii=False),
                relation.created_at,
            ),
        )
        self._connection.commit()
        return relation

    def list_relations(self, limit: int = 500) -> list[Relation]:
        rows = self._connection.execute(
            "SELECT * FROM relations WHERE status = 'accepted' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_relation(row) for row in rows]

    def add_evidence(self, evidence: Evidence, relation_id: str | None = None) -> Evidence:
        self._connection.execute(
            """
            INSERT INTO evidence(id, document_id, chunk_id, quote, source_uri, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.id,
                evidence.document_id,
                evidence.chunk_id,
                evidence.quote,
                evidence.source_uri,
                evidence.content_hash,
                evidence.created_at,
            ),
        )
        if relation_id:
            self._connection.execute(
                "INSERT INTO relation_evidence(relation_id, evidence_id) VALUES (?, ?)",
                (relation_id, evidence.id),
            )
        self._connection.commit()
        return evidence

    def neighbors(self, entity_id: str, predicate: str | None = None) -> list[Relation]:
        sql = "SELECT * FROM relations WHERE status = 'accepted' AND (source_id = ? OR target_id = ?)"
        params: list[object] = [entity_id, entity_id]
        if predicate:
            sql += " AND predicate = ?"
            params.append(predicate)
        rows = self._connection.execute(sql, params).fetchall()
        return [self._row_to_relation(row) for row in rows]

    def relation_evidence(self, relation_id: str) -> list[Evidence]:
        rows = self._connection.execute(
            """
            SELECT e.* FROM evidence e
            JOIN relation_evidence re ON re.evidence_id = e.id
            WHERE re.relation_id = ?
            """,
            (relation_id,),
        ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def add_candidate(self, candidate: CandidateFact) -> CandidateFact:
        self._connection.execute(
            """
            INSERT INTO candidate_facts(
                id, document_id, source_type, source_name, predicate,
                target_type, target_name, evidence_quote, confidence,
                source_uri, chunk_id, status, relation_id, created_at, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id, source_name, predicate, target_name, evidence_quote)
            DO NOTHING
            """,
            (
                candidate.id,
                candidate.document_id,
                candidate.source_type,
                candidate.source_name,
                candidate.predicate,
                candidate.target_type,
                candidate.target_name,
                candidate.evidence_quote,
                candidate.confidence,
                candidate.source_uri,
                candidate.chunk_id,
                candidate.status,
                candidate.relation_id,
                candidate.created_at,
                candidate.reviewed_at,
            ),
        )
        row = self._connection.execute(
            """
            SELECT * FROM candidate_facts
            WHERE document_id = ? AND source_name = ? AND predicate = ?
              AND target_name = ? AND evidence_quote = ?
            """,
            (
                candidate.document_id,
                candidate.source_name,
                candidate.predicate,
                candidate.target_name,
                candidate.evidence_quote,
            ),
        ).fetchone()
        self._connection.commit()
        if row is None:
            raise RuntimeError("Candidate fact could not be stored")
        return self._row_to_candidate(row)

    def get_candidate(self, candidate_id: str) -> CandidateFact | None:
        row = self._connection.execute(
            "SELECT * FROM candidate_facts WHERE id = ?", (candidate_id,)
        ).fetchone()
        return self._row_to_candidate(row) if row else None

    def list_candidates(self, status: str = "pending", limit: int = 100) -> list[CandidateFact]:
        rows = self._connection.execute(
            """
            SELECT * FROM candidate_facts
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
        return [self._row_to_candidate(row) for row in rows]

    def update_candidate_status(
        self, candidate_id: str, status: str, relation_id: str | None = None
    ) -> CandidateFact:
        if status not in {"pending", "accepted", "rejected"}:
            raise ValueError(f"Unsupported candidate status: {status}")
        self._connection.execute(
            """
            UPDATE candidate_facts
            SET status = ?, relation_id = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (status, relation_id, None if status == "pending" else utc_now(), candidate_id),
        )
        self._connection.commit()
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        return candidate

    def stats(self) -> dict[str, int]:
        counts = {
            "entities": self._connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            "relations": self._connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
            "evidence": self._connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
        }
        for status in ("pending", "accepted", "rejected"):
            counts[f"candidates_{status}"] = self._connection.execute(
                "SELECT COUNT(*) FROM candidate_facts WHERE status = ?", (status,)
            ).fetchone()[0]
        return counts

    def find_paths(self, source_id: str, target_id: str, max_depth: int = 3) -> list[GraphPath]:
        if not 1 <= max_depth <= 5:
            raise ValueError("max_depth must be between 1 and 5")
        if not self.get_entity(source_id) or not self.get_entity(target_id):
            return []

        found: list[GraphPath] = []
        queue: deque[tuple[str, list[PathStep], set[str]]] = deque([(source_id, [], {source_id})])
        while queue and len(found) < 20:
            current_id, steps, visited = queue.popleft()
            if len(steps) >= max_depth:
                continue
            for relation in self.neighbors(current_id):
                next_id = relation.target_id if relation.source_id == current_id else relation.source_id
                if next_id in visited:
                    continue
                source = self.get_entity(current_id)
                target = self.get_entity(next_id)
                if source is None or target is None:
                    continue
                next_steps = [*steps, PathStep(relation=relation, source=source, target=target)]
                if next_id == target_id:
                    found.append(GraphPath(steps=next_steps))
                else:
                    queue.append((next_id, next_steps, visited | {next_id}))
        return found

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Entity:
        return Entity(
            id=row["id"],
            type=row["type"],
            name=row["name"],
            aliases=json.loads(row["aliases_json"]),
            description=row["description"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_relation(row: sqlite3.Row) -> Relation:
        return Relation(
            id=row["id"],
            source_id=row["source_id"],
            predicate=row["predicate"],
            target_id=row["target_id"],
            confidence=row["confidence"],
            status=row["status"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row) -> Evidence:
        return Evidence(
            id=row["id"],
            document_id=row["document_id"],
            chunk_id=row["chunk_id"],
            quote=row["quote"],
            source_uri=row["source_uri"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> CandidateFact:
        return CandidateFact(
            id=row["id"],
            document_id=row["document_id"],
            source_type=row["source_type"],
            source_name=row["source_name"],
            predicate=row["predicate"],
            target_type=row["target_type"],
            target_name=row["target_name"],
            evidence_quote=row["evidence_quote"],
            confidence=row["confidence"],
            source_uri=row["source_uri"],
            chunk_id=row["chunk_id"],
            status=row["status"],
            relation_id=row["relation_id"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
        )
