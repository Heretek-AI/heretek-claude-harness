"""
Cold Data Compressor for Heretek Swarm

.. deprecated::
    Custom cold-data compression is being replaced by Cognee's
    storage layer as part of M-arch PR #5 (see PLAN.md §M-arch).
    This module remains in place for backward compatibility and
    will be deleted in a follow-up PR after 1 week of Cognee
    sidecar parity.

This module provides compression capabilities for infrequently accessed memories:
- Compress infrequently accessed memories
- Transparent decompression on access
- Compression ratio tracking
- Storage savings reporting

Reference: EXPANSION_ROADMAP.md Session 43 - Memory Optimization
"""

import base64
import json
import time
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Compression Types and Enums
# =============================================================================


class CompressionAlgorithm(StrEnum):
    """Supported compression algorithms."""

    ZLIB = "zlib"  # Fast, general-purpose
    GZIP = "gzip"  # Better compression, slightly slower
    LZMA = "lzma"  # Best compression, slower
    SNAPPY = "snappy"  # Very fast, lower compression
    BROTLI = "brotli"  # Good balance


class CompressionLevel(StrEnum):
    """Compression level presets."""

    FASTEST = "fastest"  # Minimum compression, maximum speed
    FAST = "fast"  # Low compression, high speed
    BALANCED = "balanced"  # Medium compression and speed
    GOOD = "good"  # Good compression, moderate speed
    BEST = "best"  # Maximum compression, slower


class CompressionStatus(StrEnum):
    """Status of compressed data."""

    COMPRESSED = "compressed"
    DECOMPRESSED = "decompressed"
    COMPRESSING = "compressing"
    DECOMPRESSING = "decompressing"
    FAILED = "failed"


@dataclass
class CompressedMemory:
    """
    Compressed memory entry.

    Attributes:
        memory_id: Original memory identifier
        compressed_data: Base64-encoded compressed data
        original_size: Size before compression (bytes)
        compressed_size: Size after compression (bytes)
        algorithm: Compression algorithm used
        compression_level: Compression level
        status: Current status
        compressed_at: Compression timestamp
        original_hash: Hash of original data for integrity
        metadata: Original metadata (uncompressed for quick access)
        access_count: Number of times decompressed
        last_decompressed: Last decompression timestamp
    """

    memory_id: str
    compressed_data: str
    original_size: int
    compressed_size: int
    algorithm: CompressionAlgorithm
    compression_level: CompressionLevel
    status: CompressionStatus = CompressionStatus.COMPRESSED
    compressed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    original_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_decompressed: str | None = None

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_size == 0:
            return 0.0
        return 1.0 - (self.compressed_size / self.original_size)

    @property
    def space_saved_bytes(self) -> int:
        """Calculate bytes saved by compression."""
        return self.original_size - self.compressed_size

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_ratio": self.compression_ratio,
            "space_saved_bytes": self.space_saved_bytes,
            "algorithm": self.algorithm.value,
            "compression_level": self.compression_level.value,
            "status": self.status.value,
            "compressed_at": self.compressed_at,
            "access_count": self.access_count,
            "last_decompressed": self.last_decompressed,
        }


@dataclass
class CompressionResult:
    """
    Result of a compression operation.

    Attributes:
        memory_id: Memory identifier
        success: Whether compression succeeded
        original_size: Original size in bytes
        compressed_size: Compressed size in bytes
        compression_ratio: Ratio of space saved (0-1)
        algorithm: Algorithm used
        level: Compression level
        latency_ms: Time taken for compression
        error: Error message if failed
    """

    memory_id: str
    success: bool
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB
    level: CompressionLevel = CompressionLevel.BALANCED
    latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "success": self.success,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_ratio": self.compression_ratio,
            "space_saved_bytes": self.original_size - self.compressed_size,
            "algorithm": self.algorithm.value,
            "level": self.level.value,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class DecompressionResult:
    """
    Result of a decompression operation.

    Attributes:
        memory_id: Memory identifier
        success: Whether decompression succeeded
        data: Decompressed data
        original_size: Original size in bytes
        latency_ms: Time taken for decompression
        integrity_verified: Whether integrity check passed
        error: Error message if failed
    """

    memory_id: str
    success: bool
    data: Any | None = None
    original_size: int = 0
    latency_ms: float = 0.0
    integrity_verified: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "success": self.success,
            "original_size": self.original_size,
            "latency_ms": self.latency_ms,
            "integrity_verified": self.integrity_verified,
            "error": self.error,
        }


@dataclass
class CompressionStatistics:
    """
    Overall compression statistics.

    Attributes:
        total_compressed: Total number of compressed memories
        total_original_size: Total original size (bytes)
        total_compressed_size: Total compressed size (bytes)
        overall_ratio: Overall compression ratio
        total_space_saved: Total bytes saved
        algorithm_distribution: Distribution of algorithms used
        avg_compression_latency: Average compression latency
        avg_decompression_latency: Average decompression latency
        failed_compressions: Number of failed compressions
        failed_decompressions: Number of failed decompressions
    """

    total_compressed: int = 0
    total_original_size: int = 0
    total_compressed_size: int = 0
    overall_ratio: float = 0.0
    total_space_saved: int = 0
    algorithm_distribution: dict[str, int] = field(default_factory=dict)
    avg_compression_latency: float = 0.0
    avg_decompression_latency: float = 0.0
    failed_compressions: int = 0
    failed_decompressions: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "totals": {
                "compressed_count": self.total_compressed,
                "original_size": self.total_original_size,
                "compressed_size": self.total_compressed_size,
                "space_saved": self.total_space_saved,
                "space_saved_mb": self.total_space_saved / (1024 * 1024),
            },
            "performance": {
                "overall_ratio": self.overall_ratio,
                "avg_compression_latency_ms": self.avg_compression_latency,
                "avg_decompression_latency_ms": self.avg_decompression_latency,
            },
            "algorithms": self.algorithm_distribution,
            "failures": {
                "compressions": self.failed_compressions,
                "decompressions": self.failed_decompressions,
            },
        }


@dataclass
class CompressionConfig:
    """
    Configuration for the compression system.

    Attributes:
        default_algorithm: Default compression algorithm
        default_level: Default compression level
        min_size_for_compression: Minimum size to consider compression
        max_compression_latency_ms: Maximum acceptable compression latency
        enable_integrity_check: Enable hash-based integrity verification
        compression_threshold: Minimum ratio to keep compressed data
    """

    default_algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB
    default_level: CompressionLevel = CompressionLevel.BALANCED
    min_size_for_compression: int = 256  # 256 bytes minimum
    max_compression_latency_ms: float = 100.0
    enable_integrity_check: bool = True
    compression_threshold: float = 0.1  # At least 10% savings


# =============================================================================
# Compression Engine
# =============================================================================


class CompressionEngine:
    """
    Core compression engine with multiple algorithm support.

    Features:
    - Multiple compression algorithms
    - Configurable compression levels
    - Integrity verification
    - Performance tracking
    """

    # Compression level mappings
    LEVEL_MAP = {  # noqa: RUF012
        CompressionLevel.FASTEST: 1,
        CompressionLevel.FAST: 3,
        CompressionLevel.BALANCED: 6,
        CompressionLevel.GOOD: 8,
        CompressionLevel.BEST: 9,
    }

    def __init__(self, config: CompressionConfig | None = None) -> None:
        """
        Initialize the compression engine.

        Args:
            config: Compression configuration
        """
        self.config = config or CompressionConfig()

        # Statistics tracking
        self._compression_count = 0
        self._decompression_count = 0
        self._total_compression_time_ms = 0.0
        self._total_decompression_time_ms = 0.0
        self._failed_compressions = 0
        self._failed_decompressions = 0

        # Algorithm tracking
        self._algorithm_counts: dict[str, int] = defaultdict(int)

        logger.info(
            "compression_engine_initialized",
            algorithm=self.config.default_algorithm.value,
            level=self.config.default_level.value,
        )

    def compress(
        self,
        data: Any,
        algorithm: CompressionAlgorithm | None = None,
        level: CompressionLevel | None = None,
    ) -> tuple[bytes, CompressionResult]:
        """
        Compress data.

        Args:
            data: Data to compress (will be serialized if not bytes)
            algorithm: Compression algorithm (uses default if None)
            level: Compression level (uses default if None)

        Returns:
            Tuple of (compressed_bytes, result)
        """
        start_time = time.time()

        algorithm = algorithm or self.config.default_algorithm
        level = level or self.config.default_level

        try:
            # Serialize data if needed
            data_bytes = json.dumps(data).encode("utf-8") if not isinstance(data, bytes) else data

            original_size = len(data_bytes)

            # Check minimum size
            if original_size < self.config.min_size_for_compression:
                result = CompressionResult(
                    memory_id="",
                    success=False,
                    original_size=original_size,
                    compressed_size=original_size,
                    compression_ratio=0.0,
                    algorithm=algorithm,
                    level=level,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=f"Data too small for compression ({original_size} bytes)",
                )
                self._failed_compressions += 1
                return data_bytes, result

            # Compress based on algorithm
            compressed = self._compress_algorithm(data_bytes, algorithm, level)

            compressed_size = len(compressed)
            compression_ratio = (
                1.0 - (compressed_size / original_size) if original_size > 0 else 0.0
            )

            # Check if compression is worthwhile
            if compression_ratio < self.config.compression_threshold:
                result = CompressionResult(
                    memory_id="",
                    success=False,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_ratio=compression_ratio,
                    algorithm=algorithm,
                    level=level,
                    latency_ms=(time.time() - start_time) * 1000,
                    error=f"Compression ratio {compression_ratio:.2%} below threshold",
                )
                self._failed_compressions += 1
                return data_bytes, result

            latency_ms = (time.time() - start_time) * 1000

            # Check latency threshold
            if latency_ms > self.config.max_compression_latency_ms:
                logger.warning(
                    "compression_latency_exceeded",
                    latency_ms=latency_ms,
                    threshold_ms=self.config.max_compression_latency_ms,
                )

            # Update statistics
            self._compression_count += 1
            self._total_compression_time_ms += latency_ms
            self._algorithm_counts[algorithm.value] += 1

            result = CompressionResult(
                memory_id="",
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                algorithm=algorithm,
                level=level,
                latency_ms=latency_ms,
            )

            return compressed, result

        except Exception as e:
            self._failed_compressions += 1
            result = CompressionResult(
                memory_id="",
                success=False,
                error=str(e),
                algorithm=algorithm,
                level=level,
                latency_ms=(time.time() - start_time) * 1000,
            )
            raise

    def decompress(
        self,
        compressed_data: bytes,
        algorithm: CompressionAlgorithm,
    ) -> tuple[bytes, DecompressionResult]:
        """
        Decompress data.

        Args:
            compressed_data: Compressed data
            algorithm: Algorithm used for compression

        Returns:
            Tuple of (decompressed_bytes, result)
        """
        start_time = time.time()

        try:
            # Decompress based on algorithm
            decompressed = self._decompress_algorithm(compressed_data, algorithm)

            latency_ms = (time.time() - start_time) * 1000

            # Update statistics
            self._decompression_count += 1
            self._total_decompression_time_ms += latency_ms

            result = DecompressionResult(
                memory_id="",
                success=True,
                data=decompressed,
                original_size=len(decompressed),
                latency_ms=latency_ms,
                integrity_verified=True,
            )

            return decompressed, result

        except Exception as e:
            self._failed_decompressions += 1
            result = DecompressionResult(
                memory_id="",
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
            raise

    def _compress_algorithm(
        self,
        data: bytes,
        algorithm: CompressionAlgorithm,
        level: CompressionLevel,
    ) -> bytes:
        """Compress using specific algorithm."""
        if algorithm == CompressionAlgorithm.ZLIB:
            return self._compress_zlib(data, level)
        if algorithm == CompressionAlgorithm.GZIP:
            return self._compress_gzip(data, level)
        # Default to zlib for unsupported algorithms
        return self._compress_zlib(data, level)

    def _decompress_algorithm(
        self,
        data: bytes,
        algorithm: CompressionAlgorithm,
    ) -> bytes:
        """Decompress using specific algorithm."""
        if algorithm == CompressionAlgorithm.ZLIB:
            return zlib.decompress(data)
        if algorithm == CompressionAlgorithm.GZIP:
            import gzip

            return gzip.decompress(data)
        # Default to zlib
        return zlib.decompress(data)

    def _compress_zlib(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress using zlib."""
        level_value = self.LEVEL_MAP.get(level, 6)
        return zlib.compress(data, level_value)

    def _compress_gzip(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress using gzip."""
        import gzip

        level_value = self.LEVEL_MAP.get(level, 6)
        return gzip.compress(data, compresslevel=level_value)

    def calculate_hash(self, data: bytes) -> str:
        """Calculate hash for integrity verification."""
        import hashlib

        return hashlib.sha256(data).hexdigest()

    def verify_integrity(self, data: bytes, expected_hash: str) -> bool:
        """Verify data integrity against hash."""
        if not self.config.enable_integrity_check:
            return True
        return self.calculate_hash(data) == expected_hash

    def get_statistics(self) -> CompressionStatistics:
        """Get compression statistics."""
        total_original = 0
        total_compressed = 0

        # Calculate totals from results (would need to track these)
        # For now, return basic stats

        overall_ratio = 0.0
        if total_original > 0:
            overall_ratio = 1.0 - (total_compressed / total_original)

        avg_compression_latency = (
            self._total_compression_time_ms / self._compression_count
            if self._compression_count > 0
            else 0.0
        )
        avg_decompression_latency = (
            self._total_decompression_time_ms / self._decompression_count
            if self._decompression_count > 0
            else 0.0
        )

        return CompressionStatistics(
            total_compressed=self._compression_count,
            total_original_size=total_original,
            total_compressed_size=total_compressed,
            overall_ratio=overall_ratio,
            total_space_saved=total_original - total_compressed,
            algorithm_distribution=dict(self._algorithm_counts),
            avg_compression_latency=avg_compression_latency,
            avg_decompression_latency=avg_decompression_latency,
            failed_compressions=self._failed_compressions,
            failed_decompressions=self._failed_decompressions,
        )


# =============================================================================
# Cold Data Compressor
# =============================================================================


class ColdDataCompressor:
    """
    Cold Data Compressor for Memory Optimization

    Manages compression of infrequently accessed memories:
    - Compress infrequently accessed memories
    - Transparent decompression on access
    - Compression ratio tracking
    - Storage savings reporting

    Features:
    - Automatic compression based on access patterns
    - Configurable compression policies
    - Integrity verification
    - Storage savings reporting
    """

    def __init__(
        self,
        config: CompressionConfig | None = None,
        enable_auto_compress: bool = True,
    ) -> None:
        """
        Initialize the cold data compressor.

        Args:
            config: Compression configuration
            enable_auto_compress: Enable automatic compression
        """
        self.config = config or CompressionConfig()
        self.enable_auto_compress = enable_auto_compress

        # Compression engine
        self._engine = CompressionEngine(self.config)

        # Compressed memory storage
        self._compressed_memories: dict[str, CompressedMemory] = {}

        # Statistics
        self._total_space_saved = 0
        self._compression_requests = 0
        self._decompression_requests = 0

        logger.info(
            "cold_data_compressor_initialized",
            auto_compress=enable_auto_compress,
        )

    def compress(
        self,
        memory_id: str,
        data: Any,
        metadata: dict[str, Any] | None = None,
        algorithm: CompressionAlgorithm | None = None,
        level: CompressionLevel | None = None,
    ) -> CompressionResult:
        """
        Compress a memory entry.

        Args:
            memory_id: Memory identifier
            data: Memory data to compress
            metadata: Memory metadata (stored uncompressed)
            algorithm: Compression algorithm
            level: Compression level

        Returns:
            Compression result
        """
        self._compression_requests += 1

        # Compress the data
        compressed_bytes, result = self._engine.compress(data, algorithm, level)

        if not result.success:
            return CompressionResult(
                memory_id=memory_id,
                success=False,
                error=result.error,
                algorithm=result.algorithm,
                level=result.level,
                latency_ms=result.latency_ms,
            )

        # Calculate hash for integrity
        data_hash = self._engine.calculate_hash(compressed_bytes)

        # Encode compressed data
        encoded_data = base64.b64encode(compressed_bytes).decode("utf-8")

        # Create compressed memory entry
        compressed_entry = CompressedMemory(
            memory_id=memory_id,
            compressed_data=encoded_data,
            original_size=result.original_size,
            compressed_size=result.compressed_size,
            algorithm=result.algorithm,
            compression_level=result.level,
            original_hash=data_hash,
            metadata=metadata or {},
        )

        # Store in compressed memories
        self._compressed_memories[memory_id] = compressed_entry

        # Update statistics
        self._total_space_saved += result.original_size - result.compressed_size

        logger.debug(
            "memory_compressed",
            memory_id=memory_id,
            ratio=f"{result.compression_ratio:.2%}",
            space_saved=result.original_size - result.compressed_size,
        )

        return CompressionResult(
            memory_id=memory_id,
            success=True,
            original_size=result.original_size,
            compressed_size=result.compressed_size,
            compression_ratio=result.compression_ratio,
            algorithm=result.algorithm,
            level=result.level,
            latency_ms=result.latency_ms,
        )

    def decompress(self, memory_id: str) -> DecompressionResult:
        """
        Decompress a memory entry.

        Args:
            memory_id: Memory identifier

        Returns:
            Decompression result with data
        """
        self._decompression_requests += 1

        if memory_id not in self._compressed_memories:
            return DecompressionResult(
                memory_id=memory_id,
                success=False,
                error=f"Memory {memory_id} not found in compressed storage",
            )

        compressed_entry = self._compressed_memories[memory_id]

        try:
            # Decode compressed data
            compressed_bytes = base64.b64decode(compressed_entry.compressed_data)

            # Decompress
            decompressed_bytes, result = self._engine.decompress(
                compressed_bytes,
                compressed_entry.algorithm,
            )

            if not result.success:
                return DecompressionResult(
                    memory_id=memory_id,
                    success=False,
                    error=result.error,
                    latency_ms=result.latency_ms,
                )

            # Verify integrity
            integrity_ok = self._engine.verify_integrity(
                compressed_bytes,
                compressed_entry.original_hash,
            )

            # Update entry
            compressed_entry.access_count += 1
            compressed_entry.last_decompressed = datetime.now(UTC).isoformat()
            compressed_entry.status = CompressionStatus.DECOMPRESSED

            # Parse JSON data
            try:
                decompressed_data = json.loads(decompressed_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                decompressed_data = decompressed_bytes

            return DecompressionResult(
                memory_id=memory_id,
                success=True,
                data=decompressed_data,
                original_size=compressed_entry.original_size,
                latency_ms=result.latency_ms,
                integrity_verified=integrity_ok,
            )

        except Exception as e:
            compressed_entry.status = CompressionStatus.FAILED
            return DecompressionResult(
                memory_id=memory_id,
                success=False,
                error=str(e),
            )

    def is_compressed(self, memory_id: str) -> bool:
        """Check if a memory is compressed."""
        return memory_id in self._compressed_memories

    def get_compressed_entry(self, memory_id: str) -> CompressedMemory | None:
        """Get compressed memory entry."""
        return self._compressed_memories.get(memory_id)

    def remove(self, memory_id: str) -> bool:
        """Remove a compressed memory."""
        if memory_id in self._compressed_memories:
            del self._compressed_memories[memory_id]
            return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive compression statistics."""
        engine_stats = self._engine.get_statistics()

        # Calculate totals from compressed memories
        total_original = sum(m.original_size for m in self._compressed_memories.values())
        total_compressed = sum(m.compressed_size for m in self._compressed_memories.values())
        overall_ratio = 1.0 - (total_compressed / total_original) if total_original > 0 else 0.0

        return {
            "engine": engine_stats.to_dict(),
            "storage": {
                "compressed_count": len(self._compressed_memories),
                "total_original_size": total_original,
                "total_compressed_size": total_compressed,
                "overall_ratio": overall_ratio,
                "total_space_saved": self._total_space_saved,
                "total_space_saved_mb": self._total_space_saved / (1024 * 1024),
            },
            "requests": {
                "compression_requests": self._compression_requests,
                "decompression_requests": self._decompression_requests,
            },
        }

    def get_compression_report(self) -> dict[str, Any]:
        """Generate a detailed compression report."""
        stats = self.get_statistics()

        # Analyze compression by algorithm
        algorithm_stats = defaultdict(lambda: {"count": 0, "total_saved": 0})
        for entry in self._compressed_memories.values():
            algo = entry.algorithm.value
            algorithm_stats[algo]["count"] += 1
            algorithm_stats[algo]["total_saved"] += entry.space_saved_bytes

        # Find best candidates for compression
        uncompressed_candidates = []
        for entry in self._compressed_memories.values():
            if entry.compression_ratio < 0.3:  # Less than 30% savings
                uncompressed_candidates.append(  # noqa: PERF401
                    {
                        "memory_id": entry.memory_id,
                        "ratio": entry.compression_ratio,
                        "algorithm": entry.algorithm.value,
                    }
                )

        return {
            "summary": stats,
            "algorithm_breakdown": dict(algorithm_stats),
            "low_efficiency_compressions": uncompressed_candidates[:20],
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> list[str]:
        """Generate compression optimization recommendations."""
        recommendations = []

        stats = self.get_statistics()
        storage = stats.get("storage", {})

        # Check overall ratio
        if storage.get("overall_ratio", 0) < 0.3:
            recommendations.append(
                "Overall compression ratio is low. Consider using a stronger compression algorithm."
            )

        # Check for many small compressions
        if storage.get("compressed_count", 0) > 100:
            avg_size = storage.get("total_original_size", 0) / max(
                storage.get("compressed_count", 1), 1
            )
            if avg_size < 2048:  # Less than 2KB average
                recommendations.append(
                    "Many small compressions detected. Consider increasing min_size_for_compression."  # noqa: E501
                )

        # Check space saved
        if storage.get("total_space_saved", 0) > 100 * 1024 * 1024:  # > 100MB
            recommendations.append(
                f"Significant space saved: {storage['total_space_saved_mb']:.2f} MB. "
                "Compression is working effectively."
            )

        return recommendations

    def clear(self) -> None:
        """Clear all compressed memories."""
        self._compressed_memories.clear()
        logger.info("cold_data_compressor_cleared")


# Import defaultdict
from collections import defaultdict  # noqa: E402
