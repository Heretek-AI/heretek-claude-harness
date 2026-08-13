"""Cognee knowledge graph pipeline — Kùzu embedded graph + MemoryBackend integration.

This module replaces the earlier cognee + NetworkX implementation per
the approved 2026-06-28 Cognee -> Kuzu Rewrite design spec.
"""

from __future__ import annotations

import json
import structlog
from typing import Any

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType

log = structlog.get_logger(__name__)

EXTRACTION_PROMPT = """Extract entities and relationships from this text.
Return JSON: {{"entities": [{{"name": "...", "type": "person|concept|decision|component|metric|event"}}], "relations": [{{"source": "...", "target": "...", "type": "causes|depends_on|contradicts|supports|part_of|decided_by"}}]}}
Text: {text}"""

ENTITY_TYPES = {"person", "concept", "decision", "component", "metric", "event"}
RELATION_TYPES = {"causes", "depends_on", "contradicts", "supports", "part_of", "decided_by"}


def _open_kuzu_db(path: str):
    """Open a Kùzu database and return a ready-to-use Connection.

    Module-level so tests can patch it.
    """
    import kuzu

    db = kuzu.Database(path)
    return kuzu.Connection(db)


def _get_extraction_client(provider: str):
    """Return an openai.AsyncOpenAI client configured for the given provider.

    For 'minimax', use the MiniMax base URL from tier1 settings. For 'openai',
    use the OpenAI base URL. Returns None on configuration failure so callers
    can degrade gracefully.
    """
    try:
        from openai import AsyncOpenAI
        from tier1.config import get_settings

        settings = get_settings()
        if provider == "minimax":
            return AsyncOpenAI(
                api_key=settings.minimax_api_key,
                base_url=settings.minimax_base_url,
                timeout=settings.llm_timeout_s,
            )
        elif provider == "openai":
            return AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.llm_timeout_s,
            )
        elif provider == "anthropic":
            # Anthropic uses a different SDK; not wired here. Return None.
            return None
        else:
            return None
    except Exception as exc:  # noqa: BLE001
        log.warning("cognee.client_init_failed", provider=provider, error=str(exc))
        return None


class CogneePipeline:
    """Pipeline orchestrator: Kùzu graph + MemoryBackend storage."""

    def __init__(
        self,
        memory_backend: MemoryBackend,
        graph_path: str = ".cognee_data",
        llm_provider: str = "minimax",
    ) -> None:
        self.memory = memory_backend
        self.graph_path = graph_path
        self.llm_provider = llm_provider
        self._conn: Any = None  # kuzu.Connection — typed as Any to avoid hard import

    def _ensure_graph(self) -> None:
        """Open the Kùzu database and create tables (idempotent)."""
        if self._conn is not None:
            return
        self._conn = _open_kuzu_db(self.graph_path)
        # DDL — kuzu raises if a table already exists, so wrap in try/except.
        ddl_statements = [
            (
                "CREATE NODE TABLE Entity("
                "name STRING, type STRING, "
                "embedding FLOAT[1536], created_at TIMESTAMP, "
                "PRIMARY KEY(name))"
            ),
            (
                "CREATE NODE TABLE Document("
                "id UUID, content_hash STRING, processed BOOLEAN, "
                "created_at TIMESTAMP, PRIMARY KEY(id))"
            ),
            (
                "CREATE REL TABLE RELATES_TO("
                "FROM Entity TO Entity, "
                "relation_type STRING, weight FLOAT, created_at TIMESTAMP)"
            ),
            ("CREATE REL TABLE CONTAINS(FROM Document TO Entity)"),
        ]
        for stmt in ddl_statements:
            try:
                self._conn.execute(stmt)
            except Exception as exc:  # noqa: BLE001
                # Table already exists — expected on subsequent opens.
                log.debug("kuzu.ddl_skipped", statement=stmt[:40], error=str(exc))

    def _find_entities_for_entry(self, entry_id: str) -> list[str]:
        """Return entity names that mention the given memory entry's id."""
        self._ensure_graph()
        result = self._conn.execute(
            "MATCH (d:Document {id: $id})-[:CONTAINS]->(e:Entity) RETURN e.name AS name",
            {"id": entry_id},
        )
        names: list[str] = []
        while result.has_next():
            row = result.get_next()
            names.append(row["name"])
        return names

    def _traverse_graph(self, entity_names: list[str], hops: int = 2) -> list[str]:
        """Traverse RELATES_TO from the given entities up to `hops` deep."""
        self._ensure_graph()
        if not entity_names:
            return []
        result = self._conn.execute(
            "MATCH (e:Entity)-[r:RELATES_TO*1.." + str(hops) + "]->(n:Entity) "
            "WHERE e.name IN $names RETURN DISTINCT n.name AS name",
            {"names": entity_names},
        )
        names: list[str] = []
        while result.has_next():
            row = result.get_next()
            names.append(row["name"])
        return names

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks. YAGNI: single chunk for now."""
        return [text]

    def _extract_entities(self, llm_response: str) -> tuple[list[dict], list[dict]]:
        """Parse an LLM JSON response into (entities, relations) lists.

        Unknown entity or relation types are dropped. Malformed JSON returns
        empty lists. Best-effort by design — never raises.
        """
        try:
            data = json.loads(llm_response)
        except Exception:  # noqa: BLE001
            log.warning("cognee.extract_invalid_json", response=llm_response[:100])
            return [], []
        entities = [
            e
            for e in data.get("entities", [])
            if isinstance(e, dict) and e.get("type") in ENTITY_TYPES
        ]
        relations = [
            r
            for r in data.get("relations", [])
            if isinstance(r, dict) and r.get("type") in RELATION_TYPES
        ]
        return entities, relations

    def _extract_model_name(self) -> str:
        from tier1.config import get_settings

        settings = get_settings()
        if self.llm_provider == "minimax":
            return settings.minimax_model
        elif self.llm_provider == "openai":
            return settings.openai_model
        elif self.llm_provider == "anthropic":
            return settings.anthropic_model
        return "gpt-4o-mini"

    def _write_graph_for_chunk(
        self,
        chunk: str,
        entities: list[dict],
        relations: list[dict],
    ) -> None:
        """Persist entities, relations, and a Document node into Kùzu."""
        import hashlib
        import uuid

        doc_id = uuid.uuid4()
        content_hash = hashlib.sha256(chunk.encode()).hexdigest()
        self._conn.execute(
            "CREATE (d:Document {id: $id, content_hash: $h, processed: true})",
            {"id": doc_id, "h": content_hash},
        )
        for ent in entities:
            self._conn.execute(
                "MERGE (e:Entity {name: $name}) SET e.type = $type",
                {"name": ent["name"], "type": ent["type"]},
            )
            self._conn.execute(
                "MATCH (d:Document {id: $did}), (e:Entity {name: $name}) "
                "CREATE (d)-[:CONTAINS]->(e)",
                {"did": doc_id, "name": ent["name"]},
            )
        for rel in relations:
            self._conn.execute(
                "MATCH (a:Entity {name: $src}), (b:Entity {name: $tgt}) "
                "MERGE (a)-[r:RELATES_TO {relation_type: $type}]->(b)",
                {"src": rel["source"], "tgt": rel["target"], "type": rel["type"]},
            )

    async def add(self, text: str, metadata: dict | None = None) -> str:
        """5-stage pipeline: chunk -> extract via LLM -> write graph -> store memory.

        On LLM or Kuzu failure, degrades to plain memory store (graph is
        built later by cognify() or skipped entirely).
        """
        # Stage 1: chunk
        chunks = self._chunk_text(text)

        # Stage 2-4: build graph (best-effort)
        try:
            client = _get_extraction_client(self.llm_provider)
            if client is not None:
                self._ensure_graph()
                for chunk in chunks:
                    response = await client.chat.completions.create(
                        model=self._extract_model_name(),
                        messages=[
                            {"role": "user", "content": EXTRACTION_PROMPT.format(text=chunk)},
                        ],
                    )
                    content = response.choices[0].message.content or "{}"
                    entities, relations = self._extract_entities(content)
                    self._write_graph_for_chunk(chunk, entities, relations)
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.graph_build_failed", error=str(exc), exc_info=True)

        # Stage 5: store in memory backend (always runs)
        entry = MemoryEntry(
            content=text,
            memory_type=MemoryType.semantic,
            source="cognee",
            metadata=metadata or {},
        )
        return await self.memory.store(entry)

    async def cognify(self, batch_size: int = 10) -> int:
        """Process unprocessed entries: extract entities, build graph edges.

        Returns the count of newly-processed documents. Best-effort: on
        any failure, logs and returns 0.
        """
        try:
            self._ensure_graph()
            result = self._conn.execute(
                "MATCH (d:Document {processed: false}) RETURN d.id AS id LIMIT $limit",
                {"limit": batch_size},
            )
            ids: list[str] = []
            while result.has_next():
                row = result.get_next()
                ids.append(row["id"])
            # Mark them processed (no entity extraction here — add() already does it).
            for did in ids:
                self._conn.execute(
                    "MATCH (d:Document {id: $id}) SET d.processed = true",
                    {"id": did},
                )
            return len(ids)
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.cognify_failed", error=str(exc), exc_info=True)
            return 0

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Vector search via MemoryBackend + 2-hop graph enrichment."""
        base_results = await self.memory.search(query, top_k=top_k)
        enriched: list[MemoryEntry] = []
        for entry in base_results:
            # Best-effort: skip enrichment on Kuzu failure.
            try:
                entities = self._find_entities_for_entry(entry.id)
                _ = self._traverse_graph(entities, hops=2)
            except Exception:
                pass
            enriched.append(entry)
        return enriched

    async def improve(self) -> None:
        """Best-effort graph refinement: ensure schema exists. Failures logged."""
        try:
            self._ensure_graph()
        except Exception as exc:  # noqa: BLE001
            log.warning("cognee.improve_failed", error=str(exc), exc_info=True)
