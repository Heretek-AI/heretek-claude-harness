"""
Historian Agent - Memory and context provider for the Triad.

The Historian provides:
- Long-term memory storage and retrieval
- Context provision for deliberations
- Historical pattern recognition
- Knowledge synthesis from past executions
- Lineage tracking for decisions

Features:
- LRU cache with configurable max size for context and patterns
- Cache eviction when limits are reached
- JSONL event log to ``.gsd/historian.jsonl``
"""

import asyncio
import contextlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from swarms import Agent

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.historian.types import LRUCache
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)

# Session 44: Collective Learning Integration
from heretek_swarm.collective.learning import PatternExtractor

# Session 44: Consensus Integration
from heretek_swarm.consensus.swarm_deliberation import SwarmDeliberationEngine
from heretek_swarm.knowledge.unified_access import KnowledgeQueryResult, UnifiedKnowledgeAccess

# Session 44: Memory Optimization Integration
from heretek_swarm.memory.access_patterns import AccessPatternAnalyzer
from heretek_swarm.memory.base import DualTierMemory, MemoryEntry
from heretek_swarm.memory.cognee_reader import CogneeMemoryReader

# Session 44: Zero-Trust Validation
from heretek_swarm.security.zero_trust import ZeroTrustValidator

_HISTORIAN_FILE = Path(".gsd/historian.jsonl")
logger = structlog.get_logger("HistorianAgent")


class HistorianAgent(
    HealthReportingMixin,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Historian Agent - Memory and context provider.

    The Historian is the memory specialist for the Triad:
    - Stores and retrieves long-term memories
    - Provides context for current deliberations
    - Recognizes historical patterns
    - Synthesizes knowledge from past executions
    - Tracks decision lineage
    """

    def __init__(
        self,
        agent_id: str = "historian",
        name: str = "Historian",
        description: str = "Memory and context provider for the Triad",
        swarms_agent: Agent | None = None,
        memory_system: DualTierMemory | None = None,
        context_window: int = 10,
        context_cache_max_size: int = 100,
        pattern_cache_max_size: int = 50,
        pattern_extractor: PatternExtractor | None = None,
        deliberation_engine: SwarmDeliberationEngine | None = None,
        access_analyzer: AccessPatternAnalyzer | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
        cognee_reader: CogneeMemoryReader | None = None,
        db_pool: Any | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the Historian agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            swarms_agent: Optional Swarms Agent for LLM capabilities
            memory_system: Optional dual-tier memory system
            context_window: Number of recent memories to include as context
            context_cache_max_size: Maximum context cache entries (default: 100)
            pattern_cache_max_size: Maximum pattern cache entries (default: 50)
            **kwargs: Additional arguments
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=["triad", "memory", "context", "history", "lineage"],
            capabilities=[
                "memory-storage",
                "memory-retrieval",
                "context-provision",
                "pattern-recognition",
                "lineage-tracking",
            ],
            swarms_agent=swarms_agent,
            **kwargs,
        )

        self.memory_system = memory_system or DualTierMemory()
        self.rag_pipeline = kwargs.get("rag_pipeline")
        self.context_window = context_window

        # Historian-specific state with LRU caches
        self.decision_lineage: dict[str, list[str]] = {}
        self.pattern_cache = LRUCache(max_size=pattern_cache_max_size)
        self.context_cache = LRUCache(max_size=context_cache_max_size)

        # Unified knowledge access layer
        self.knowledge_access: UnifiedKnowledgeAccess | None = None

        # Session 44: Collective Learning Integration
        self.pattern_extractor = pattern_extractor or PatternExtractor(
            min_support=3, min_confidence=0.6
        )

        # Session 44: Consensus Integration
        self.deliberation_engine = deliberation_engine or SwarmDeliberationEngine(
            max_rounds=5, consensus_threshold=0.75, min_participants=2
        )

        # Session 44: Memory Optimization Integration
        self.access_analyzer = access_analyzer or AccessPatternAnalyzer()

        # Session 44: Zero-Trust Validation
        self.zero_trust_validator = zero_trust_validator or ZeroTrustValidator()

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        # Optional asyncpg connection pool for Postgres-backed event store

        # M-arch PR #2: optional Cognee reader for graph-augmented context
        # Default is None → no Cognee calls. Set COGNEE_ENABLED=true to opt in.
        self.cognee_reader = cognee_reader or CogneeMemoryReader()
        self._db_pool: Any | None = db_pool  # may be injected later via internal_state

        # JSONL event log path — read from package-level _HISTORIAN_FILE
        # so tests can patch heretek_swarm.actors.historian._HISTORIAN_FILE
        # and have it picked up during initialize().
        self._jsonl_path: Path | None = None

        # Event log infrastructure — shared queue, one writer at a time
        self._jsonl_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._writer_task: asyncio.Task | None = None
        self._using_pg: bool = False  # True → _pg_writer, False → _jsonl_writer

        logger.info(f"[{self.agent_id}] Historian agent initialized")

    async def initialize(self) -> None:
        """Initialize the Historian agent."""
        # Initialize memory system
        await self.memory_system.initialize()

        # Re-read _HISTORIAN_FILE from the package module at init time
        # so tests can patch it before calling initialize().
        import heretek_swarm.actors.historian as _h_mod

        self._jsonl_path = _h_mod._HISTORIAN_FILE  # noqa: SLF001

        # Initialize unified knowledge access layer
        if self.rag_pipeline:
            self.knowledge_access = UnifiedKnowledgeAccess(
                memory_system=self.memory_system,
                rag_pipeline=self.rag_pipeline,
            )
            logger.info(f"[{self.agent_id}] Unified knowledge access initialized")
        else:
            self.knowledge_access = UnifiedKnowledgeAccess(
                memory_system=self.memory_system,
                rag_pipeline=None,
            )
            logger.info(f"[{self.agent_id}] Knowledge access initialized (memory only)")

        # Event log: create shared queue and start the appropriate writer.
        # If a db_pool is available (injected by the supervisor or constructor),
        # start the Postgres writer; otherwise fall back to the JSONL writer.
        self._jsonl_queue = asyncio.Queue()
        db_pool = self._db_pool or self.get_state("_db_pool")
        if db_pool is not None:
            self._using_pg = True
            self._writer_task = asyncio.create_task(self._pg_writer(db_pool))
            logger.info(f"[{self.agent_id}] Starting Postgres event writer")
        else:
            self._using_pg = False
            self._writer_task = asyncio.create_task(self._jsonl_writer())
            logger.info(f"[{self.agent_id}] Starting JSONL event writer")

        # Register message handlers
        self.register_handler("store_memory", self._handle_store_memory)
        self.register_handler("retrieve_context", self._handle_retrieve_context)
        self.register_handler("query_history", self._handle_query_history)
        self.register_handler("track_lineage", self._handle_track_lineage)
        self.register_handler("pattern_match", self._handle_pattern_match)
        self.register_handler("unified_query", self._handle_unified_query)
        self.register_handler("log_event", self._handle_log_event)

        logger.info(f"[{self.agent_id}] Historian initialization complete")

    async def process_message(self, message: ActorMessage) -> None:
        """Process incoming messages."""
        handler = self._message_handlers.get(message.message_type)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.exception(
                    f"[{self.agent_id}] Error processing message {message.message_type}: {e}",  # noqa: G004

                )
                self.error_count += 1
                # Send error response if reply_to is specified
                if message.content.get("reply_to"):
                    await self.send(
                        topic=message.content["reply_to"],
                        content={
                            "message_type": "error_response",
                            "error": str(e),
                            "original_message_type": message.message_type,
                        },
                        correlation_id=message.correlation_id,
                    )
        else:
            logger.warning(f"[{self.agent_id}] Unhandled message type: {message.message_type}")

    async def _handle_store_memory(self, message: ActorMessage) -> None:
        """Handle memory storage requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("store_memory", message.content)
            if validated:
                content = validated.content
                metadata = validated.metadata
                ttl = validated.ttl
                persistent = validated.persistent
            else:
                # Fallback to unvalidated access
                content = message.content.get("content")
                metadata = message.content.get("metadata", {})
                ttl = message.content.get("ttl")
                persistent = message.content.get("persistent", False)
        except ValueError:
            logger.error(f"[{self.agent_id}] Store memory validation failed: {e}")
            return

        logger.debug(f"[{self.agent_id}] Storing memory")

        entry = await self.store_memory(
            content=content,
            metadata=metadata,
            ttl=ttl,
            persistent=persistent,
        )

        reply_topic = message.content.get("reply_to", "memory")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "store_memory_response",
                "memory_id": entry.id,
                "created_at": entry.created_at,
                "persistent": persistent,
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_retrieve_context(self, message: ActorMessage) -> None:
        """Handle context retrieval requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("retrieve_context", message.content)
            if validated:
                # Extract topic from filters or use default
                topic = (
                    validated.filters.get("topic")
                    if hasattr(validated, "filters")
                    else message.content.get("topic")
                )
                filters = (
                    validated.filters
                    if hasattr(validated, "filters")
                    else message.content.get("filters", {})
                )
                window_size = (
                    validated.limit
                    if hasattr(validated, "limit")
                    else message.content.get("window_size", self.context_window)
                )
            else:
                # Fallback to unvalidated access
                topic = message.content.get("topic")
                filters = message.content.get("filters", {})
                window_size = message.content.get("window_size", self.context_window)
        except ValueError:
            logger.error(f"[{self.agent_id}] Retrieve context validation failed: {e}")
            return

        logger.debug(f"[{self.agent_id}] Retrieving context for: {topic}")

        context = await self.retrieve_context(
            topic=topic,
            filters=filters,
            window_size=window_size,
        )

        reply_topic = message.content.get("reply_to", "context")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "retrieve_context_response",
                "topic": topic,
                "context": context,
                "context_size": len(context),
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_query_history(self, message: ActorMessage) -> None:
        """Handle history query requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("query_history", message.content)
            if validated:
                query_text = validated.query_text
                filters = validated.filters
                limit = validated.limit
            else:
                # Fallback to unvalidated access
                query_text = message.content.get("query_text")
                filters = message.content.get("filters", {})
                limit = message.content.get("limit", 10)
        except ValueError:
            logger.error(f"[{self.agent_id}] Query history validation failed: {e}")
            return

        logger.debug(f"[{self.agent_id}] Querying history: {query_text}")

        results = await self.query_history(
            query_text=query_text,
            filters=filters,
            limit=limit,
        )

        reply_topic = message.content.get("reply_to", "history")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "query_history_response",
                "query": query_text,
                "results": results,
                "result_count": len(results),
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_track_lineage(self, message: ActorMessage) -> None:
        """Handle lineage tracking requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("track_lineage", message.content)
            if validated:
                decision_id = validated.decision_id
                parent_ids = validated.parent_ids
            else:
                # Fallback to unvalidated access
                decision_id = message.content.get("decision_id")
                parent_ids = message.content.get("parent_ids", [])
        except ValueError:
            logger.error(f"[{self.agent_id}] Track lineage validation failed: {e}")
            return

        logger.debug(f"[{self.agent_id}] Tracking lineage for: {decision_id}")

        await self.track_decision_lineage(
            decision_id=decision_id,
            parent_ids=parent_ids,
        )

        reply_topic = message.content.get("reply_to", "lineage")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "track_lineage_response",
                "decision_id": decision_id,
                "parent_ids": parent_ids,
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_pattern_match(self, message: ActorMessage) -> None:
        """Handle pattern matching requests with validation."""
        # P2-7 fix: Validate input before processing
        try:
            validated = self._validate_message_content("pattern_match", message.content)
            if validated:
                current_situation = (
                    validated.query_text
                    if hasattr(validated, "query_text")
                    else message.content.get("situation")
                )
            else:
                # Fallback to unvalidated access
                current_situation = message.content.get("situation")
        except ValueError:
            logger.error(f"[{self.agent_id}] Pattern match validation failed: {e}")
            return

        logger.debug(f"[{self.agent_id}] Matching patterns for: {current_situation}")

        patterns = await self.match_patterns(current_situation)

        reply_topic = message.content.get("reply_to", "patterns")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "pattern_match_response",
                "situation": current_situation,
                "matched_patterns": patterns,
                "pattern_count": len(patterns),
            },
            correlation_id=message.correlation_id,
        )

    async def _handle_unified_query(self, message: ActorMessage) -> None:
        """Handle unified knowledge query requests using the knowledge access layer."""
        try:
            query_text = message.content.get("query")
            sources = message.content.get("sources", ["memory", "rag"])
            limit = message.content.get("limit", 10)
            rerank = message.content.get("rerank", True)
            diversity_lambda = message.content.get("diversity_lambda", 0.5)
            filters = message.content.get("filters", {})

            if not query_text:
                logger.error(f"[{self.agent_id}] Unified query requires query text")
                return

            logger.debug(f"[{self.agent_id}] Executing unified query: {query_text[:50]}")

            # Execute unified query
            result = await self.knowledge_access.query(
                query=query_text,
                sources=sources,
                limit=limit,
                rerank=rerank,
                diversity_lambda=diversity_lambda,
                filters=filters,
            )

            # Send response
            reply_topic = message.content.get("reply_to", "knowledge")
            await self.send(
                topic=reply_topic,
                content={
                    "message_type": "unified_query_response",
                    "query": query_text,
                    "results": result.to_dict(),
                    "entry_count": len(result.entries),
                    "total_results": result.total_results,
                    "query_time_ms": result.query_time_ms,
                    "reranking_applied": result.reranking_applied,
                },
                correlation_id=message.correlation_id,
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Unified query error: {e}")
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "error_response",
                        "error": str(e),
                    },
                    correlation_id=message.correlation_id,
                )

    async def unified_query(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 10,
        rerank: bool = True,
        diversity_lambda: float = 0.5,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeQueryResult:
        """
        Execute a unified knowledge query.

        Args:
            query: Search query string
            sources: List of sources (memory, rag)
            limit: Maximum results
            rerank: Apply MMR reranking
            diversity_lambda: MMR diversity parameter
            filters: Additional filters

        Returns:
            KnowledgeQueryResult with merged and reranked entries
        """
        if not self.knowledge_access:
            logger.warning(f"[{self.agent_id}] Knowledge access not initialized")
            return KnowledgeQueryResult(entries=[], total_results=0)

        return await self.knowledge_access.query(
            query=query,
            sources=sources or ["memory", "rag"],
            limit=limit,
            rerank=rerank,
            diversity_lambda=diversity_lambda,
            filters=filters or {},
        )

    async def store_memory(
        self,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        persistent: bool = False,
        lineage: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Memory content
            metadata: Additional metadata
            ttl: Time to live in seconds
            persistent: Store in persistent tier
            lineage: Parent memory IDs

        Returns:
            Stored memory entry
        """
        # Add agent metadata
        # P2-1 fix: Use timezone-aware datetime
        full_metadata = {
            **(metadata or {}),
            "agent_id": self.agent_id,
            "stored_at": datetime.now(UTC).isoformat(),
        }

        entry = await self.memory_system.store(
            content=content,
            metadata=full_metadata,
            ttl=ttl,
            lineage=lineage,
            persistent=persistent,
        )

        logger.debug(f"[{self.agent_id}] Stored memory {entry.id}")

        return entry

    async def retrieve_context(
        self,
        topic: str,
        filters: dict[str, Any] | None = None,
        window_size: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retrieve context for a topic.

        Args:
            topic: Topic to retrieve context for
            filters: Additional filters
            window_size: Number of recent memories

        Returns:
            List of context entries
        """
        # Check cache first
        cache_key = f"{topic}:{window_size}"
        cached = self.context_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[{self.agent_id}] Context cache hit for: {topic}")
            return cached

        # Build query filters
        query_filters = filters or {}
        if topic:
            query_filters["topic"] = topic

        # Query primary memory
        results = await self.memory_system.query(
            filters=query_filters,
            limit=window_size,
        )

        context: list[dict[str, Any]] = [
            {
                "content": e.content,
                "metadata": e.metadata,
                "created_at": e.created_at,
            }
            for e in results
        ]

        # M-arch PR #2: supplement with Cognee graph-augmented context.
        # Reader is a no-op when disabled or unreachable (returns []),
        # so this never breaks the primary memory path.
        if self.cognee_reader is not None and self.cognee_reader.enabled:
            try:
                cognee_results = await self.cognee_reader.read(
                    query=topic, top_k=window_size
                )
                for hit in cognee_results:
                    context.append(
                        {
                            "content": hit.get("content", ""),
                            "metadata": {
                                "source": "cognee",
                                "score": hit.get("score"),
                                "dataset": hit.get("dataset"),
                                **(hit.get("metadata") or {}),
                            },
                            "created_at": None,
                        }
                    )
                if cognee_results:
                    logger.info(
                        f"[{self.agent_id}] Cognee supplemented {len(cognee_results)} context entries for: {topic}"
                    )
            except Exception as e:
                # Defensive: never let a supplemental source break primary retrieval
                logger.warning(
                    f"[{self.agent_id}] Cognee reader failed (suppressed): {e}"
                )

        # Update cache (with automatic LRU eviction)
        self.context_cache.set(cache_key, context)

        logger.debug(
            f"[{self.agent_id}] Retrieved {len(context)} context entries for: {topic} (cache size: {len(self.context_cache)})"  # noqa: G004,E501
        )

        return context

    async def query_history(
        self,
        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Query historical memories.

        Args:
            query_text: Text to search for
            filters: Metadata filters
            limit: Maximum results

        Returns:
            List of matching memories
        """
        results = await self.memory_system.query(
            query_text=query_text,
            filters=filters,
            limit=limit,
        )

        return [
            {
                "id": e.id,
                "content": e.content,
                "metadata": e.metadata,
                "created_at": e.created_at,
                "lineage": e.lineage,
            }
            for e in results
        ]

    async def track_decision_lineage(
        self,
        decision_id: str,
        parent_ids: list[str],
    ) -> None:
        """
        Track lineage for a decision.

        Args:
            decision_id: Decision identifier
            parent_ids: Parent memory/decision IDs
        """
        self.decision_lineage[decision_id] = parent_ids

        # Also store in memory
        await self.store_memory(
            content={
                "type": "lineage",
                "decision_id": decision_id,
                "parent_ids": parent_ids,
            },
            metadata={
                "lineage": True,
                "decision_id": decision_id,
            },
            persistent=True,
        )

        logger.debug(f"[{self.agent_id}] Tracked lineage for {decision_id}: {parent_ids}")

    async def get_lineage(self, decision_id: str) -> list[str]:
        """
        Get lineage for a decision.

        Args:
            decision_id: Decision identifier

        Returns:
            List of parent IDs
        """
        return self.decision_lineage.get(decision_id, [])

    async def match_patterns(
        self,
        situation: str,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Match current situation against historical patterns.

        Args:
            situation: Current situation description
            threshold: Similarity threshold

        Returns:
            List of matched patterns
        """
        # Check cache first
        cached = self.pattern_cache.get(situation)
        if cached is not None:
            return cached

        matched = []

        # Query for similar situations
        results = await self.memory_system.query(
            query_text=situation,
            filters={"type": "situation"},
            limit=5,
        )

        for entry in results:
            # Compute actual similarity using text comparison
            similarity = self._compute_similarity(situation, str(entry.content))
            if similarity >= threshold:
                matched.append(
                    {
                        "situation": entry.content,
                        "metadata": entry.metadata,
                        "similarity": similarity,
                    }
                )

        # Cache results (with automatic LRU eviction)
        self.pattern_cache.set(situation, matched)

        logger.debug(
            f"[{self.agent_id}] Matched {len(matched)} patterns for: {situation} (cache size: {len(self.pattern_cache)})"  # noqa: G004,E501
        )

        return matched

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute similarity between two texts using cosine similarity on character n-grams.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0.0 and 1.0
        """

        # Simple cosine similarity using character 2-grams
        def get_ngrams(text: str, n: int = 2) -> dict[str, int]:
            """Get character n-grams with frequencies."""
            text = text.lower().strip()
            ngrams = {}
            for i in range(len(text) - n + 1):
                ngram = text[i : i + n]
                ngrams[ngram] = ngrams.get(ngram, 0) + 1
            return ngrams

        def cosine_similarity(vec1: dict[str, int], vec2: dict[str, int]) -> float:
            """Compute cosine similarity between two frequency vectors."""
            # Get all unique keys
            all_keys = set(vec1.keys()) | set(vec2.keys())

            # Compute dot product and magnitudes
            dot_product = 0.0
            mag1 = 0.0
            mag2 = 0.0

            for key in all_keys:
                v1 = vec1.get(key, 0)
                v2 = vec2.get(key, 0)
                dot_product += v1 * v2
                mag1 += v1 * v1
                mag2 += v2 * v2

            if mag1 == 0 or mag2 == 0:
                return 0.0

            return dot_product / (mag1**0.5 * mag2**0.5)

        # Get n-grams for both texts
        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)

        return cosine_similarity(ngrams1, ngrams2)

    async def provide_deliberation_context(
        self,
        deliberation_id: str,
        topic: str,
    ) -> dict[str, Any]:
        """
        Provide comprehensive context for a deliberation.

        Args:
            deliberation_id: Deliberation identifier
            topic: Deliberation topic

        Returns:
            Context dictionary with relevant memories and patterns
        """
        logger.info(f"[{self.agent_id}] Providing context for deliberation: {deliberation_id}")

        # Retrieve relevant context
        context_entries = await self.retrieve_context(
            topic=topic,
            window_size=self.context_window,
        )

        # Match patterns
        patterns = await self.match_patterns(topic)

        # Get lineage if exists
        lineage = await self.get_lineage(deliberation_id)

        # P2-1 fix: Use timezone-aware datetime
        context = {
            "deliberation_id": deliberation_id,
            "topic": topic,
            "relevant_memories": context_entries,
            "matched_patterns": patterns,
            "lineage": lineage,
            "provided_at": datetime.now(UTC).isoformat(),
        }

        # Store context provision in memory
        await self.store_memory(
            content={
                "type": "context_provision",
                "deliberation_id": deliberation_id,
                "context": context,
            },
            metadata={
                "deliberation_id": deliberation_id,
                "topic": topic,
            },
            persistent=True,
        )

        return context

    async def synthesize_knowledge(
        self,
        topic: str,
        limit: int = 20,
        timeout: int = 60,  # noqa: ASYNC109
    ) -> dict[str, Any]:
        """
        Synthesize knowledge from historical executions.

        Args:
            topic: Topic to synthesize
            limit: Maximum memories to consider
            timeout: LLM call timeout in seconds (default: 60)

        Returns:
            Synthesized knowledge summary
        """
        logger.info(f"[{self.agent_id}] Synthesizing knowledge for: {topic}")

        # Retrieve relevant memories
        results = await self.memory_system.query(
            query_text=topic,
            limit=limit,
        )

        if not results:
            return {
                "topic": topic,
                "summary": "No relevant memories found",
                "confidence": 0.0,
            }

        # Synthesize (would use LLM in full implementation)
        if self.swarms_agent:
            try:
                memory_texts = [str(e.content) for e in results]
                synthesis_prompt = f"Synthesize knowledge from these memories: {memory_texts}"
                # P0-14 fix: Add timeout to LLM call
                synthesis = await self.run_with_llm(prompt=synthesis_prompt, timeout=timeout)

                # P2-1 fix: Use timezone-aware datetime
                return {
                    "topic": topic,
                    "summary": synthesis,
                    "source_count": len(results),
                    "confidence": 0.8,
                    "synthesized_at": datetime.now(UTC).isoformat(),
                }
            except TimeoutError:
                # P2-1 fix: Use timezone-aware datetime
                logger.error(f"[{self.agent_id}] Synthesis timed out after {timeout}s")
                return {
                    "topic": topic,
                    "summary": f"Synthesis timed out after {timeout}s",
                    "source_count": len(results),
                    "confidence": 0.0,
                    "error": "timeout",
                    "synthesized_at": datetime.now(UTC).isoformat(),
                }
            except Exception:
                logger.error(f"[{self.agent_id}] Synthesis error: {e}")

        # Fallback synthesis
        # P2-1 fix: Use timezone-aware datetime
        return {
            "topic": topic,
            "summary": f"Found {len(results)} relevant memories",
            "source_count": len(results),
            "confidence": 0.5,
            "synthesized_at": datetime.now(UTC).isoformat(),
        }

    def get_memory_statistics(self) -> dict[str, Any]:
        """Get memory system statistics."""
        memory_stats = self.memory_system.get_statistics()

        return {
            "total_memories": memory_stats.get("combined_total", 0),
            "decision_lineages": len(self.decision_lineage),
            "pattern_cache": self.pattern_cache.get_statistics(),
            "context_cache": self.context_cache.get_statistics(),
            "memory_details": memory_stats,
        }

    # Session 44: Collective Learning, Consensus Deliberation, and Memory Optimization
    # integration methods now provided by DeliberationMixin, LearningMixin, MemoryMixin, and PatternMixin.  # noqa: E501

    # ------------------------------------------------------------------
    # JSONL event log
    # ------------------------------------------------------------------

    async def _jsonl_writer(self) -> None:
        """Drain ``_jsonl_queue`` and write each event as a JSON line to
        ``_HISTORIAN_FILE``.

        Runs as a background ``asyncio.Task`` started during
        ``initialize()``.  The file is opened/closed per write (safe for
        concurrent readers on POSIX / NTFS).
        """
        while True:
            try:
                record = await self._jsonl_queue.get()
            except asyncio.CancelledError:
                # Task is being cancelled — exit cleanly so the
                # CancelledError propagates to the caller.
                break

            try:
                import json

                line = json.dumps(record, default=str, ensure_ascii=False)
                # Use asyncio.to_thread so file I/O does not block the
                # event loop — stdlib only, no aiofiles dependency.
                await asyncio.to_thread(self._write_jsonl_line, self._jsonl_path, line)
            except Exception:
                logger.exception(f"[{self.agent_id}] JSONL writer error")
            finally:
                self._jsonl_queue.task_done()

    @staticmethod
    def _write_jsonl_line(path: Path, line: str) -> None:
        """Synchronous file-write helper called from ``asyncio.to_thread``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "a", encoding="utf-8") as f:  # noqa: PTH123
            f.write(line)
            f.write("\n")

    # ------------------------------------------------------------------
    # Postgres-backed event writer
    # ------------------------------------------------------------------

    _CREATE_HISTORIAN_EVENTS_DDL = """
        CREATE TABLE IF NOT EXISTS historian_events (
            event_id   TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            timestamp  TIMESTAMPTZ NOT NULL,
            agent_id   TEXT NOT NULL,
            payload    JSONB NOT NULL DEFAULT '{}'
        );
    """

    _INSERT_EVENT_STMT = """
        INSERT INTO historian_events (event_id, event_type, timestamp, agent_id, payload)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (event_id) DO NOTHING;
    """

    async def _pg_writer(self, db_pool: Any) -> None:
        """Drain ``_jsonl_queue`` and insert each event as a row into the
        ``historian_events`` table.

        Runs as a background ``asyncio.Task`` started during
        ``initialize()`` when a db_pool is available.  Creates the table on
        startup via ``CREATE TABLE IF NOT EXISTS``.
        """
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(self._CREATE_HISTORIAN_EVENTS_DDL)
        except Exception:
            logger.exception(f"[{self.agent_id}] Failed to create historian_events table")
            return

        while True:
            try:
                record = await self._jsonl_queue.get()
            except asyncio.CancelledError:
                break

            try:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        self._INSERT_EVENT_STMT,
                        record["event_id"],
                        record["type"],
                        record["timestamp"],
                        record["agent_id"],
                        json.dumps(record["payload"]),
                    )
                logger.debug(f"[{self.agent_id}] PG writer: inserted event {record['event_id']}")
            except Exception:
                logger.exception(
                    f"[{self.agent_id}] PG writer error for event {record.get('event_id', '?')}"  # noqa: G004
                )
            finally:
                self._jsonl_queue.task_done()

    # ------------------------------------------------------------------
    # Event reading
    # ------------------------------------------------------------------

    async def read_events(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query past events from the Postgres-backed event store.

        Args:
            agent_id: Filter by agent identifier (optional).
            event_type: Filter by event type string (optional).
            since: ISO-8601 lower bound for ``timestamp`` (optional).
            until: ISO-8601 upper bound for ``timestamp`` (optional).
            limit: Maximum number of results (default: 100).

        Returns:
            List of event dicts with the same shape as ``log_event``::

                {
                    "event_id": str,
                    "type": str,
                    "timestamp": str (ISO-8601),
                    "agent_id": str,
                    "payload": dict,
                }

            Returns an empty list when the Postgres writer is not active
            (i.e. JSONL mode) or on query failure.
        """
        if not self._using_pg:
            return []

        db_pool = self._db_pool or self.get_state("_db_pool")
        if db_pool is None:
            logger.warning(f"[{self.agent_id}] read_events called but no db_pool available")
            return []

        # Build dynamic WHERE clause with parameterized placeholders
        conditions: list[str] = []
        params: list[Any] = []
        idx = 0  # param counter for $1, $2, … style placeholders

        if agent_id is not None:
            idx += 1
            conditions.append(f"agent_id = ${idx}")
            params.append(agent_id)
        if event_type is not None:
            idx += 1
            conditions.append(f"event_type = ${idx}")
            params.append(event_type)
        if since is not None:
            idx += 1
            conditions.append(f"timestamp >= ${idx}")
            params.append(since)
        if until is not None:
            idx += 1
            conditions.append(f"timestamp <= ${idx}")
            params.append(until)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        limit_idx = idx + 1
        query = f"""
            SELECT event_id, event_type, timestamp, agent_id, payload
            FROM historian_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${limit_idx}
        """
        params.append(limit)

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
        except Exception:
            logger.exception(f"[{self.agent_id}] read_events query failed")
            return []

        return [
            {
                "event_id": row["event_id"],
                "type": row["event_type"],
                "timestamp": (
                    row["timestamp"].isoformat()
                    if hasattr(row["timestamp"], "isoformat")
                    else str(row["timestamp"])
                ),
                "agent_id": row["agent_id"],
                "payload": dict(row["payload"]) if row["payload"] else {},
            }
            for row in rows
        ]

    async def log_event(
        self,
        event_type: str,
        agent_id: str,
        payload: dict[str, Any],
    ) -> str:
        """Enqueue a structured event record and return the generated
        ``event_id``.

        The record is written asynchronously by the background writer
        (Postgres or JSONL, whichever is active) — callers do **not**
        block on I/O.

        Schema (all fields top-level):
        - ``event_id`` — ``uuid.uuid4().hex``
        - ``type`` — the *event_type* argument
        - ``timestamp`` — ISO-8601 (UTC)
        - ``agent_id`` — the *agent_id* argument
        - ``payload`` — the *payload* dict
        """
        record: dict[str, Any] = {
            "event_id": uuid.uuid4().hex,
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "payload": payload,
        }
        await self._jsonl_queue.put(record)
        return str(record["event_id"])

    async def _handle_log_event(self, message: ActorMessage) -> None:
        """Handle ``"log_event"`` message dispatch.

        Expected ``message.content`` keys:
        - ``"event_type"`` (str, required)
        - ``"agent_id"`` (str, required)
        - ``"payload"`` (dict, required)

        Responds with ``{"message_type": "log_event_response", "event_id": ...}``.
        """
        event_type = message.content.get("event_type")
        agent_id = message.content.get("agent_id")
        payload = message.content.get("payload", {})

        if not event_type or not agent_id:
            logger.error(
                f"[{self.agent_id}] log_event missing required fields",  # noqa: G004
                extra={"content_keys": list(message.content)},
            )
            return

        event_id = await self.log_event(
            event_type=event_type,
            agent_id=agent_id,
            payload=payload,
        )

        reply_topic = message.content.get("reply_to", "history")
        await self.send(
            topic=reply_topic,
            content={
                "message_type": "log_event_response",
                "event_id": event_id,
            },
            correlation_id=message.correlation_id,
        )

    async def cleanup(self) -> None:
        """Cleanup resources — flush remaining events first."""
        # Drain remaining queue items before closing the writer
        if self._writer_task is not None and not self._writer_task.done():
            await self._jsonl_queue.join()
            self._writer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._writer_task

        # If PG mode was active, close the pool
        if self._using_pg:
            db_pool = self._db_pool or self.get_state("_db_pool")
            if db_pool is not None:
                try:
                    await db_pool.close()
                except Exception:
                    logger.exception(f"[{self.agent_id}] Error closing db_pool during cleanup")

        await self.memory_system.close()
        logger.info(f"[{self.agent_id}] Historian cleanup complete")
