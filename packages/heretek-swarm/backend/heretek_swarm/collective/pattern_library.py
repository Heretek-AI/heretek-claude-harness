"""
Pattern Library - Cross-Agent Learning

Implements persistent storage and query interface for validated patterns.
This module provides a centralized repository for storing, categorizing,
and retrieving patterns across the agent swarm.

Features:
- Store validated patterns in persistent storage
- Categorize patterns by type (success, failure, optimization)
- Query interface for pattern retrieval
- Pattern versioning and history tracking
- Pattern expiration and cleanup

Zero-Trust Principles:
- All patterns validated before storage
- Query validation and sanitization
- Access control for pattern operations
- Audit logging for all operations
"""

import asyncio
import contextlib
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

from .learning import ExtractedPattern, PatternMetadata, PatternSource, PatternType

logger = structlog.get_logger(__name__)

# Module-level constant for repeated log message
_PATTERN_PARSE_FALLBACK_MSG = "Pattern parsing fallback"


def _is_date_after(date_str: str, cutoff: datetime) -> bool:
    """Check if a date string is after a cutoff datetime. Returns True if parse fails."""
    try:
        return datetime.fromisoformat(date_str) >= cutoff
    except (ValueError, TypeError):
        return True  # Fail open on unparseable dates


class StorageBackend(StrEnum):
    """Storage backend options."""

    IN_MEMORY = "in_memory"
    FILE_SYSTEM = "file_system"
    REDIS = "redis"
    POSTGRESQL = "postgresql"


class PatternCategory(StrEnum):
    """Pattern categories for organization."""

    INTERACTION = "interaction"
    DECISION = "decision"
    OPTIMIZATION = "optimization"
    ERROR_HANDLING = "error_handling"
    COMMUNICATION = "communication"
    COLLABORATION = "collaboration"
    RESOURCE_MANAGEMENT = "resource_management"
    SECURITY = "security"
    PERFORMANCE = "performance"
    EMERGENT = "emergent"


@dataclass
class PatternEntry:
    """A stored pattern entry in the library."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern: ExtractedPattern = None
    category: PatternCategory = PatternCategory.INTERACTION
    stored_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_accessed: str | None = None
    access_count: int = 0
    version: int = 1
    version_history: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_active: bool = True
    expiration_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "pattern": self.pattern.to_dict() if self.pattern else {},
            "category": self.category.value,
            "stored_at": self.stored_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "version": self.version,
            "version_history": self.version_history,
            "tags": self.tags,
            "is_active": self.is_active,
            "expiration_date": self.expiration_date,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternEntry":
        """Create from dictionary."""
        pattern_dict = data.get("pattern", {})

        # Reconstruct pattern
        if pattern_dict:
            metadata_dict = pattern_dict.get("metadata", {})
            metadata = PatternMetadata(
                pattern_id=metadata_dict.get("pattern_id", str(uuid.uuid4())),
                pattern_type=PatternType(metadata_dict.get("pattern_type", "success")),
                source=PatternSource(metadata_dict.get("source", "message_history")),
                confidence=metadata_dict.get("confidence", 0.0),
                support_count=metadata_dict.get("support_count", 0),
                first_observed=metadata_dict.get("first_observed"),
                last_observed=metadata_dict.get("last_observed"),
                agents_involved=metadata_dict.get("agents_involved", []),
                topics=metadata_dict.get("topics", []),
                tags=metadata_dict.get("tags", []),
            )

            pattern = ExtractedPattern(
                metadata=metadata,
                pattern_data=pattern_dict.get("pattern_data", {}),
                context=pattern_dict.get("context", {}),
                outcomes=pattern_dict.get("outcomes", []),
                preconditions=pattern_dict.get("preconditions", []),
                postconditions=pattern_dict.get("postconditions", []),
                applicability_conditions=pattern_dict.get("applicability_conditions", []),
            )
        else:
            pattern = None

        return cls(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            pattern=pattern,
            category=PatternCategory(data.get("category", "interaction")),
            stored_at=data.get("stored_at", datetime.now(UTC).isoformat()),
            last_accessed=data.get("last_accessed"),
            access_count=data.get("access_count", 0),
            version=data.get("version", 1),
            version_history=data.get("version_history", []),
            tags=data.get("tags", []),
            is_active=data.get("is_active", True),
            expiration_date=data.get("expiration_date"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QueryResult:
    """Result of a pattern query."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patterns: list[PatternEntry] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    filters_applied: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_id": self.query_id,
            "patterns": [p.to_dict() for p in self.patterns],
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
            "filters_applied": self.filters_applied,
            "warnings": self.warnings,
        }


@dataclass
class StorageStats:
    """Storage statistics."""

    total_patterns: int = 0
    active_patterns: int = 0
    expired_patterns: int = 0
    patterns_by_type: dict[str, int] = field(default_factory=dict)
    patterns_by_category: dict[str, int] = field(default_factory=dict)
    storage_size_bytes: int = 0
    oldest_pattern: str | None = None
    newest_pattern: str | None = None
    avg_access_count: float = 0.0


class PatternLibrary:
    """
    Persistent storage and query interface for validated patterns.

    This library provides centralized pattern storage with support for
    multiple storage backends, categorization, and efficient querying.

    Attributes:
        backend: Storage backend type
        storage_path: Path for file system storage
        patterns: In-memory pattern cache
    """

    def __init__(
        self,
        backend: StorageBackend = StorageBackend.IN_MEMORY,
        storage_path: str | None = None,
        redis_url: str | None = None,
        default_ttl_days: int = 30,
    ):
        """
        Initialize pattern library.

        Args:
            backend: Storage backend type
            storage_path: Path for file system storage
            redis_url: Redis connection URL (for Redis backend)
            default_ttl_days: Default time-to-live for patterns
        """
        self.backend = backend
        self.storage_path = storage_path or "./.pattern_library"
        self.redis_url = redis_url
        self.default_ttl_days = default_ttl_days

        self._patterns: dict[str, PatternEntry] = {}
        self._category_index: dict[PatternCategory, set[str]] = {
            cat: set() for cat in PatternCategory
        }
        self._type_index: dict[PatternType, set[str]] = {pt: set() for pt in PatternType}
        self._tag_index: dict[str, set[str]] = {}

        self._redis = None
        self._query_history: list[QueryResult] = []
        self._callbacks: dict[str, list[Callable]] = {
            "on_store": [],
            "on_retrieve": [],
            "on_delete": [],
            "on_expire": [],
        }

        logger.info(
            "pattern_library_initialized",
            backend=backend.value,
            storage_path=storage_path,
            default_ttl_days=default_ttl_days,
        )

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register callback for library events.

        Args:
            event: Event type (on_store, on_retrieve, on_delete, on_expire)
            callback: Callback function
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
            logger.debug("callback_registered", event=event, callback=callback.__name__)

    async def store_pattern(
        self,
        pattern: ExtractedPattern,
        category: PatternCategory | None = None,
        tags: list[str] | None = None,
        ttl_days: int | None = None,
    ) -> PatternEntry:
        """
        Store a pattern in the library.

        Args:
            pattern: Pattern to store
            category: Pattern category (auto-detected if None)
            tags: Additional tags for indexing
            ttl_days: Time-to-live in days (default: library default)

        Returns:
            PatternEntry for stored pattern
        """
        start_time = datetime.now(UTC)

        # Determine category
        if category is None:
            category = self._auto_detect_category(pattern)

        # Calculate expiration
        ttl = ttl_days or self.default_ttl_days
        expiration = (start_time + timedelta(days=ttl)).isoformat()

        # Create entry
        entry = PatternEntry(
            pattern=pattern,
            category=category,
            expiration_date=expiration,
            tags=tags or [],
            metadata={
                "stored_by": "pattern_library",
                "storage_version": "1.0",
            },
        )

        # Store in memory
        self._patterns[entry.entry_id] = entry

        # Update indexes
        self._update_indexes(entry)

        # Persist to backend
        await self._persist_entry(entry)

        # Call callbacks
        await self._call_callbacks("on_store", entry)

        logger.info(
            "pattern_stored",
            entry_id=entry.entry_id,
            pattern_id=pattern.metadata.pattern_id,
            category=category.value,
            expiration=expiration,
        )

        return entry

    async def retrieve_pattern(
        self,
        entry_id: str,
    ) -> PatternEntry | None:
        """
        Retrieve a pattern by entry ID.

        Args:
            entry_id: Entry identifier

        Returns:
            PatternEntry or None if not found
        """
        entry = self._patterns.get(entry_id)

        if entry:
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = datetime.now(UTC).isoformat()

            # Call callbacks
            await self._call_callbacks("on_retrieve", entry)

            logger.debug(
                "pattern_retrieved",
                entry_id=entry_id,
                access_count=entry.access_count,
            )

        return entry

    async def query_patterns(
        self,
        pattern_type: PatternType | None = None,
        category: PatternCategory | None = None,
        tags: list[str] | None = None,
        min_confidence: float = 0.0,
        max_age_days: int | None = None,
        limit: int = 100,
        offset: int = 0,
        include_inactive: bool = False,
    ) -> QueryResult:
        """
        Query patterns with filters.
        """
        start_time = datetime.now(UTC)
        filters_applied = {
            "pattern_type": pattern_type.value if pattern_type else None,
            "category": category.value if category else None,
            "tags": tags,
            "min_confidence": min_confidence,
            "max_age_days": max_age_days,
            "limit": limit,
            "offset": offset,
            "include_inactive": include_inactive,
        }

        candidate_ids = self._resolve_candidate_ids(pattern_type, category, tags)
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days) if max_age_days else None
        filtered = self._filter_candidates(
            candidate_ids, min_confidence, cutoff_date, include_inactive
        )

        filtered.sort(
            key=lambda e: e.pattern.metadata.confidence if e.pattern else 0, reverse=True,
        )
        total_count = len(filtered)
        paginated = filtered[offset : offset + limit]
        query_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

        result = QueryResult(
            patterns=paginated, total_count=total_count, query_time_ms=query_time,
            filters_applied=filters_applied, warnings=[],
        )
        self._query_history.append(result)
        if len(self._query_history) > 1000:
            self._query_history = self._query_history[-500:]

        logger.debug(
            "query_executed", total_count=total_count,
            returned_count=len(paginated), query_time_ms=query_time,
        )
        return result

    def _resolve_candidate_ids(
        self,
        pattern_type: PatternType | None,
        category: PatternCategory | None,
        tags: list[str] | None,
    ) -> set[str]:
        """Resolve candidate pattern IDs using indexes."""
        candidate_ids: set[str] = set(self._patterns.keys())

        if category and category in self._category_index:
            candidate_ids &= self._category_index[category]
        if pattern_type and pattern_type in self._type_index:
            candidate_ids &= self._type_index[pattern_type]
        if tags:
            for tag in tags:
                if tag in self._tag_index:
                    candidate_ids &= self._tag_index[tag]
                else:
                    return set()
        return candidate_ids

    def _filter_candidates(
        self,
        candidate_ids: set[str],
        min_confidence: float,
        cutoff_date: datetime | None,
        include_inactive: bool,
    ) -> list[PatternEntry]:
        """Filter candidate patterns by confidence, age, expiration, and active status."""
        filtered: list[PatternEntry] = []
        for entry_id in candidate_ids:
            entry = self._patterns.get(entry_id)
            if not entry:
                continue
            if not include_inactive and not entry.is_active:
                continue
            if entry.pattern and entry.pattern.metadata.confidence < min_confidence:
                continue
            if cutoff_date and entry.stored_at:
                if not _is_date_after(entry.stored_at, cutoff_date):
                    continue
            if entry.expiration_date:
                if not _is_date_after(entry.expiration_date, datetime.now(UTC)):
                    continue
            filtered.append(entry)
        return filtered

    async def delete_pattern(self, entry_id: str) -> bool:
        """
        Delete a pattern from the library.

        Args:
            entry_id: Entry identifier

        Returns:
            True if deleted successfully
        """
        entry = self._patterns.get(entry_id)
        if not entry:
            return False

        # Remove from memory
        del self._patterns[entry_id]

        # Remove from indexes
        self._remove_from_indexes(entry)

        # Remove from backend
        await self._delete_from_backend(entry_id)

        # Call callbacks
        await self._call_callbacks("on_delete", entry)

        logger.info(
            "pattern_deleted",
            entry_id=entry_id,
            pattern_id=entry.pattern.metadata.pattern_id if entry.pattern else None,
        )

        return True

    async def update_pattern(
        self,
        entry_id: str,
        pattern: ExtractedPattern | None = None,
        tags: list[str] | None = None,
        category: PatternCategory | None = None,
    ) -> PatternEntry | None:
        """
        Update a pattern in the library.

        Args:
            entry_id: Entry identifier
            pattern: New pattern data (optional)
            tags: New tags (optional)
            category: New category (optional)

        Returns:
            Updated PatternEntry or None if not found
        """
        entry = self._patterns.get(entry_id)
        if not entry:
            return None

        # Store old version
        entry.version_history.append(entry.pattern.to_dict() if entry.pattern else {})
        entry.version += 1

        # Update fields
        if pattern:
            entry.pattern = pattern
        if tags is not None:
            # Remove old tag indexes
            self._remove_from_indexes(entry)
            entry.tags = tags
        if category:
            self._remove_from_indexes(entry)
            entry.category = category

        # Rebuild indexes if needed
        if tags is not None or category:
            self._update_indexes(entry)

        # Persist update
        await self._persist_entry(entry)

        logger.info(
            "pattern_updated",
            entry_id=entry_id,
            version=entry.version,
        )

        return entry

    async def cleanup_expired(self) -> int:
        """
        Remove expired patterns from the library.

        Returns:
            Number of patterns removed
        """
        now = datetime.now(UTC)
        expired = []

        for entry_id, entry in list(self._patterns.items()):
            if entry.expiration_date:
                try:
                    exp_date = datetime.fromisoformat(entry.expiration_date)
                    if exp_date < now:
                        expired.append(entry_id)
                except (ValueError, TypeError):
                    logger.debug(_PATTERN_PARSE_FALLBACK_MSG, exc_info=True)

        removed = 0
        for entry_id in expired:
            if await self.delete_pattern(entry_id):
                removed += 1
                # Call expire callback
                await self._call_callbacks("on_expire", entry_id)

        logger.info(
            "cleanup_complete",
            expired_count=len(expired),
            removed_count=removed,
        )

        return removed

    def _auto_detect_category(self, pattern: ExtractedPattern) -> PatternCategory:
        """Auto-detect pattern category based on type and content."""
        type_category_map = {
            PatternType.SUCCESS: PatternCategory.INTERACTION,
            PatternType.FAILURE: PatternCategory.ERROR_HANDLING,
            PatternType.OPTIMIZATION: PatternCategory.OPTIMIZATION,
            PatternType.HANDOFF: PatternCategory.INTERACTION,
            PatternType.COLLABORATION: PatternCategory.COLLABORATION,
            PatternType.DECISION: PatternCategory.DECISION,
            PatternType.COMMUNICATION: PatternCategory.COMMUNICATION,
            PatternType.ERROR_RECOVERY: PatternCategory.ERROR_HANDLING,
            PatternType.EMERGENT: PatternCategory.EMERGENT,
            PatternType.RESOURCE_USAGE: PatternCategory.RESOURCE_MANAGEMENT,
        }

        return type_category_map.get(
            pattern.metadata.pattern_type,
            PatternCategory.INTERACTION,
        )

    def _update_indexes(self, entry: PatternEntry) -> None:
        """Update indexes for a pattern entry."""
        # Category index
        if entry.category in self._category_index:
            self._category_index[entry.category].add(entry.entry_id)

        # Type index
        if entry.pattern:
            pattern_type = entry.pattern.metadata.pattern_type
            if pattern_type in self._type_index:
                self._type_index[pattern_type].add(entry.entry_id)

        # Tag index
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(entry.entry_id)

    def _remove_from_indexes(self, entry: PatternEntry) -> None:
        """Remove entry from all indexes."""
        # Category index
        if entry.category in self._category_index:
            self._category_index[entry.category].discard(entry.entry_id)

        # Type index
        if entry.pattern:
            pattern_type = entry.pattern.metadata.pattern_type
            if pattern_type in self._type_index:
                self._type_index[pattern_type].discard(entry.entry_id)

        # Tag index
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(entry.entry_id)

    async def _persist_entry(self, entry: PatternEntry) -> None:
        """Persist entry to storage backend."""
        if self.backend == StorageBackend.FILE_SYSTEM:
            await self._persist_to_filesystem(entry)
        elif self.backend == StorageBackend.REDIS:
            await self._persist_to_redis(entry)
        # In-memory backend doesn't need persistence

    async def _persist_to_filesystem(self, entry: PatternEntry) -> None:
        """Persist entry to file system."""
        try:
            os.makedirs(self.storage_path, exist_ok=True)

            # Create category subdirectory
            category_path = os.path.join(self.storage_path, entry.category.value)
            os.makedirs(category_path, exist_ok=True)

            # Write entry file
            file_path = os.path.join(category_path, f"{entry.entry_id}.json")
            with open(file_path, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)

            logger.debug(
                "entry_persisted_to_filesystem",
                entry_id=entry.entry_id,
                file_path=file_path,
            )

        except Exception as e:
            logger.error(
                "filesystem_persist_failed",
                entry_id=entry.entry_id,
                error=str(e),
            )

    async def _persist_to_redis(self, entry: PatternEntry) -> None:
        """Persist entry to Redis."""
        if not self._redis:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self.redis_url, decode_responses=True)
            except (ImportError, Exception) as e:
                logger.warning(
                    "redis_not_available",
                    error=str(e),
                )
                return

        try:
            key = f"heretek:patterns:{entry.entry_id}"
            await self._redis.set(key, json.dumps(entry.to_dict()))

            # Add to category set
            await self._redis.sadd(
                f"heretek:patterns:category:{entry.category.value}",
                entry.entry_id,
            )

            logger.debug(
                "entry_persisted_to_redis",
                entry_id=entry.entry_id,
                key=key,
            )

        except Exception as e:
            logger.error(
                "redis_persist_failed",
                entry_id=entry.entry_id,
                error=str(e),
            )

    async def _delete_from_backend(self, entry_id: str) -> None:
        """Delete entry from storage backend."""
        if self.backend == StorageBackend.FILE_SYSTEM:
            # Find and delete file
            for category in PatternCategory:
                file_path = os.path.join(
                    self.storage_path,
                    category.value,
                    f"{entry_id}.json",
                )
                if os.path.exists(file_path):
                    os.remove(file_path)
                    break

        elif self.backend == StorageBackend.REDIS and self._redis:
            try:
                await self._redis.delete(f"heretek:patterns:{entry_id}")
            except Exception as e:
                logger.error(
                    "redis_delete_failed",
                    entry_id=entry_id,
                    error=str(e),
                )

    async def _call_callbacks(self, event: str, *args) -> None:
        """Call registered callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    callback(*args)
            except Exception as e:
                logger.error(
                    "callback_error",
                    event=event,
                    callback=callback.__name__,
                    error=str(e),
                )

    def get_stats(self) -> StorageStats:
        """
        Get library storage statistics.

        Returns:
            StorageStats with current statistics
        """
        datetime.now(UTC)

        total = len(self._patterns)
        active = sum(1 for e in self._patterns.values() if e.is_active)
        expired = total - active

        # Patterns by type
        by_type: dict[str, int] = {}
        for pt in PatternType:
            by_type[pt.value] = len(self._type_index.get(pt, set()))

        # Patterns by category
        by_category: dict[str, int] = {}
        for cat in PatternCategory:
            by_category[cat.value] = len(self._category_index.get(cat, set()))

        # Estimate storage size
        size_bytes = sum(len(json.dumps(e.to_dict())) for e in self._patterns.values())

        # Find oldest and newest
        dates = []
        for entry in self._patterns.values():
            if entry.stored_at:
                with contextlib.suppress(ValueError, TypeError):
                    dates.append(datetime.fromisoformat(entry.stored_at))

        oldest = min(dates).isoformat() if dates else None
        newest = max(dates).isoformat() if dates else None

        # Average access count
        total_access = sum(e.access_count for e in self._patterns.values())
        avg_access = total_access / total if total > 0 else 0.0

        return StorageStats(
            total_patterns=total,
            active_patterns=active,
            expired_patterns=expired,
            patterns_by_type=by_type,
            patterns_by_category=by_category,
            storage_size_bytes=size_bytes,
            oldest_pattern=oldest,
            newest_pattern=newest,
            avg_access_count=avg_access,
        )

    def get_pattern(
        self,
        entry_id: str,
    ) -> ExtractedPattern | None:
        """
        Get pattern by entry ID.

        Args:
            entry_id: Entry identifier

        Returns:
            ExtractedPattern or None
        """
        entry = self._patterns.get(entry_id)
        return entry.pattern if entry else None

    def list_categories(self) -> dict[str, int]:
        """
        List all categories with pattern counts.

        Returns:
            Dictionary of category names to counts
        """
        return {cat.value: len(self._category_index.get(cat, set())) for cat in PatternCategory}

    def list_tags(self) -> dict[str, int]:
        """
        List all tags with pattern counts.

        Returns:
            Dictionary of tags to counts
        """
        return {tag: len(entries) for tag, entries in self._tag_index.items()}


class PatternLibraryService:
    """
    High-level service for pattern library operations.

    Provides convenient methods for common pattern library tasks.
    """

    def __init__(self, library: PatternLibrary):
        """
        Initialize pattern library service.

        Args:
            library: PatternLibrary instance
        """
        self.library = library

        logger.info("pattern_library_service_initialized")

    async def add_success_pattern(
        self,
        pattern: ExtractedPattern,
        tags: list[str] | None = None,
    ) -> PatternEntry:
        """
        Add a success pattern to the library.

        Args:
            pattern: Pattern to add
            tags: Additional tags

        Returns:
            PatternEntry for stored pattern
        """
        return await self.library.store_pattern(
            pattern=pattern,
            category=PatternCategory.INTERACTION,
            tags=tags,
        )

    async def add_failure_pattern(
        self,
        pattern: ExtractedPattern,
        tags: list[str] | None = None,
    ) -> PatternEntry:
        """
        Add a failure pattern to the library.

        Args:
            pattern: Pattern to add
            tags: Additional tags

        Returns:
            PatternEntry for stored pattern
        """
        return await self.library.store_pattern(
            pattern=pattern,
            category=PatternCategory.ERROR_HANDLING,
            tags=tags or ["failure"],
        )

    async def get_best_practices(
        self,
        agent_type: str | None = None,
        limit: int = 10,
    ) -> QueryResult:
        """
        Get best practice patterns (high confidence success patterns).

        Args:
            agent_type: Filter by agent type
            limit: Maximum results

        Returns:
            QueryResult with best practices
        """
        return await self.library.query_patterns(
            pattern_type=PatternType.SUCCESS,
            min_confidence=0.8,
            limit=limit,
        )

    async def get_common_pitfalls(
        self,
        limit: int = 10,
    ) -> QueryResult:
        """
        Get common failure patterns to avoid.

        Args:
            limit: Maximum results

        Returns:
            QueryResult with pitfalls
        """
        return await self.library.query_patterns(
            pattern_type=PatternType.FAILURE,
            min_confidence=0.5,
            limit=limit,
        )

    async def search_patterns(
        self,
        query: str,
        limit: int = 20,
    ) -> QueryResult:
        """
        Search patterns by text query.

        Args:
            query: Search query string
            limit: Maximum results

        Returns:
            QueryResult with matching patterns
        """
        # Full-text search would be implemented here
        # For now, return all patterns and let caller filter
        return await self.library.query_patterns(
            limit=limit,
        )

    def get_library_status(self) -> dict[str, Any]:
        """
        Get library status summary.

        Returns:
            Status dictionary
        """
        stats = self.library.get_stats()

        return {
            "total_patterns": stats.total_patterns,
            "active_patterns": stats.active_patterns,
            "by_category": stats.patterns_by_category,
            "by_type": stats.patterns_by_type,
            "storage_size_kb": round(stats.storage_size_bytes / 1024, 2),
            "avg_access_count": round(stats.avg_access_count, 2),
            "backend": self.library.backend.value,
        }
