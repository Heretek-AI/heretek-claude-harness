-- Migration: Create memory optimization tables
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Support memory optimization features including access pattern tracking,
--          tier classification, compression metadata, and prefetch cache state
-- Session: 45 - Database Migrations
--
-- This migration creates tables for:
-- 1. memory_access_logs - Access pattern tracking for memory optimization
-- 2. memory_tier_state - Current tier classification for memory items
-- 3. compression_metadata - Compression tracking and statistics
-- 4. prefetch_cache - Pre-fetch cache state and hit tracking
--
-- All tables are idempotent (CREATE IF NOT EXISTS) and include rollback support

-- ============================================================================
-- SECTION 1: Memory Access Logs Table
-- ============================================================================
-- Tracks memory access patterns for optimization decisions.
-- Records every memory access with timing and context information.

CREATE TABLE IF NOT EXISTS memory_access_logs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Memory reference
    memory_id UUID NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    -- References swarm_memories.id or other memory sources

    -- Access details
    access_type VARCHAR(50) NOT NULL DEFAULT 'read',
    -- Types: read, write, update, delete, search

    -- Agent context
    agent_id VARCHAR(255) NOT NULL,
    session_id UUID,
    workflow_id UUID,

    -- Access timing
    access_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_duration_ms FLOAT,
    -- Time taken to complete the access

    -- Access context
    access_context JSONB DEFAULT '{}',
    query_vector vector(1536),
    -- Vector used for similarity search (if applicable)

    -- Access result
    result_size_bytes INTEGER,
    cache_hit BOOLEAN DEFAULT FALSE,
    tier_accessed VARCHAR(20),
    -- Which tier was accessed: hot, warm, cold, archive

    -- Pattern metadata
    is_sequential BOOLEAN DEFAULT FALSE,
    -- Whether this access is part of a sequential pattern

    pattern_group_id UUID,
    -- Groups related accesses for pattern detection

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- SECTION 2: Memory Tier State Table
-- ============================================================================
-- Tracks current tier classification for memory items.
-- Supports dynamic tiering based on access patterns.

CREATE TABLE IF NOT EXISTS memory_tier_state (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Memory reference
    memory_id UUID NOT NULL,
    memory_type VARCHAR(50) NOT NULL,

    -- Current tier
    current_tier VARCHAR(20) NOT NULL DEFAULT 'hot',
    -- Tiers: hot, warm, cold, archive

    -- Tier history
    previous_tier VARCHAR(20),
    tier_changes INTEGER DEFAULT 0,
    last_tier_change_at TIMESTAMP WITH TIME ZONE,

    -- Tiering criteria
    access_frequency FLOAT DEFAULT 0.0,
    -- Accesses per hour

    recency_score FLOAT DEFAULT 1.0,
    -- Based on time since last access

    importance_score FLOAT DEFAULT 0.5,
    -- Intrinsic importance of the memory

    size_bytes INTEGER,
    -- Memory size for storage cost calculation

    -- Tiering decisions
    tier_algorithm VARCHAR(50) DEFAULT 'lru_with_importance',
    -- Algorithm used for tier decision

    next_review_at TIMESTAMP WITH TIME ZONE,
    -- When to re-evaluate tier

    -- Storage location
    storage_location VARCHAR(255),
    -- Physical storage path or identifier

    compression_enabled BOOLEAN DEFAULT FALSE,
    compression_algorithm VARCHAR(50),
    compressed_size_bytes INTEGER,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(memory_id, memory_type)
);

-- ============================================================================
-- SECTION 3: Compression Metadata Table
-- ============================================================================
-- Tracks compression state and statistics for memory items.

CREATE TABLE IF NOT EXISTS compression_metadata (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Memory reference
    memory_id UUID NOT NULL,
    memory_type VARCHAR(50) NOT NULL,

    -- Compression state
    is_compressed BOOLEAN DEFAULT FALSE,
    compression_algorithm VARCHAR(50),
    -- Algorithms: gzip, lz4, zstd, snappy

    -- Size metrics
    original_size_bytes INTEGER NOT NULL,
    compressed_size_bytes INTEGER,
    compression_ratio FLOAT DEFAULT 1.0,
    -- original_size / compressed_size

    -- Compression quality
    compression_level INTEGER,
    -- Algorithm-specific compression level

    lossless BOOLEAN DEFAULT TRUE,
    -- Whether compression is lossless

    -- Performance metrics
    compression_time_ms FLOAT,
    decompression_time_ms FLOAT,

    -- Access tracking
    decompression_count INTEGER DEFAULT 0,
    -- Number of times decompressed

    last_decompressed_at TIMESTAMP WITH TIME ZONE,

    -- Compression context
    compression_context JSONB DEFAULT '{}',
    -- Additional metadata about compression

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint
    UNIQUE(memory_id, memory_type)
);

-- ============================================================================
-- SECTION 4: Prefetch Cache Table
-- ============================================================================
-- Tracks prefetch cache state and effectiveness.

CREATE TABLE IF NOT EXISTS prefetch_cache (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cache entry identity
    cache_key VARCHAR(500) NOT NULL,
    cache_type VARCHAR(50) NOT NULL DEFAULT 'prediction',
    -- Types: prediction, pattern, recent, frequent

    -- Cached content reference
    memory_ids UUID[] DEFAULT '{}',
    -- List of memory IDs in this cache entry

    -- Prefetch metadata
    prefetch_trigger VARCHAR(100),
    -- What triggered the prefetch

    prediction_confidence FLOAT DEFAULT 0.5,
    -- Confidence in prefetch prediction

    pattern_id UUID,
    -- Reference to collective_patterns if pattern-based

    -- Cache state
    state VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- States: pending, ready, expired, invalidated

    -- Hit/miss tracking
    hit_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMP WITH TIME ZONE,

    -- Timing
    prefetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    -- When cache entry expires

    -- Cache location
    cache_location VARCHAR(255),
    -- Where the prefetched data is stored

    -- Size
    total_size_bytes INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(cache_key, cache_type)
);

-- ============================================================================
-- SECTION 5: Indexes
-- ============================================================================

-- Memory Access Logs indexes
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_memory ON memory_access_logs(memory_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_agent ON memory_access_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_session ON memory_access_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_type ON memory_access_logs(access_type);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_timestamp ON memory_access_logs(access_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_cache_hit ON memory_access_logs(cache_hit);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_tier ON memory_access_logs(tier_accessed);
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_pattern_group ON memory_access_logs(pattern_group_id);

-- Composite index for pattern analysis
CREATE INDEX IF NOT EXISTS idx_memory_access_logs_agent_timestamp ON memory_access_logs(agent_id, access_timestamp DESC);

-- Memory Tier State indexes
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_memory ON memory_tier_state(memory_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_tier ON memory_tier_state(current_tier);
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_frequency ON memory_tier_state(access_frequency DESC);
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_recency ON memory_tier_state(recency_score DESC);
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_review ON memory_tier_state(next_review_at);
CREATE INDEX IF NOT EXISTS idx_memory_tier_state_compressed ON memory_tier_state(compression_enabled);

-- Compression Metadata indexes
CREATE INDEX IF NOT EXISTS idx_compression_metadata_memory ON compression_metadata(memory_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_compression_metadata_algorithm ON compression_metadata(compression_algorithm);
CREATE INDEX IF NOT EXISTS idx_compression_metadata_ratio ON compression_metadata(compression_ratio DESC);
CREATE INDEX IF NOT EXISTS idx_compression_metadata_compressed ON compression_metadata(is_compressed);

-- Prefetch Cache indexes
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_key ON prefetch_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_type ON prefetch_cache(cache_type);
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_state ON prefetch_cache(state);
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_expires ON prefetch_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_pattern ON prefetch_cache(pattern_id);

-- Index for hit rate calculation
CREATE INDEX IF NOT EXISTS idx_prefetch_cache_hits ON prefetch_cache(hit_count DESC);

-- ============================================================================
-- SECTION 6: Functions
-- ============================================================================

-- Function to update timestamp on row update
CREATE OR REPLACE FUNCTION update_memory_optimization_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to log memory access
CREATE OR REPLACE FUNCTION log_memory_access(
    memory_id_param UUID,
    memory_type_param VARCHAR,
    access_type_param VARCHAR,
    agent_id_param VARCHAR,
    session_id_param UUID DEFAULT NULL,
    duration_ms_param FLOAT DEFAULT NULL,
    cache_hit_param BOOLEAN DEFAULT FALSE,
    tier_param VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    new_log_id UUID;
BEGIN
    INSERT INTO memory_access_logs (
        memory_id,
        memory_type,
        access_type,
        agent_id,
        session_id,
        access_duration_ms,
        cache_hit,
        tier_accessed
    ) VALUES (
        memory_id_param,
        memory_type_param,
        access_type_param,
        agent_id_param,
        session_id_param,
        duration_ms_param,
        cache_hit_param,
        tier_param
    ) RETURNING id INTO new_log_id;

    -- Update tier state access frequency
    UPDATE memory_tier_state
    SET
        access_frequency = access_frequency + (1.0 / 24.0), -- Increment hourly rate
        last_tier_change_at = NOW()
    WHERE memory_id = memory_id_param AND memory_type = memory_type_param;

    RETURN new_log_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update memory tier
CREATE OR REPLACE FUNCTION update_memory_tier(
    memory_id_param UUID,
    memory_type_param VARCHAR,
    new_tier VARCHAR,
    algorithm_param VARCHAR DEFAULT 'lru_with_importance'
)
RETURNS void AS $$
DECLARE
    old_tier VARCHAR;
BEGIN
    SELECT current_tier INTO old_tier
    FROM memory_tier_state
    WHERE memory_id = memory_id_param AND memory_type = memory_type_param;

    IF FOUND AND old_tier IS DISTINCT FROM new_tier THEN
        UPDATE memory_tier_state
        SET
            previous_tier = old_tier,
            current_tier = new_tier,
            tier_changes = tier_changes + 1,
            last_tier_change_at = NOW(),
            tier_algorithm = algorithm_param,
            updated_at = NOW()
        WHERE memory_id = memory_id_param AND memory_type = memory_type_param;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to record compression
CREATE OR REPLACE FUNCTION record_compression(
    memory_id_param UUID,
    memory_type_param VARCHAR,
    algorithm VARCHAR,
    original_size INTEGER,
    compressed_size INTEGER,
    compression_time_ms FLOAT DEFAULT NULL,
    level_param INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    new_compression_id UUID;
    ratio FLOAT;
BEGIN
    ratio := CASE WHEN compressed_size > 0 THEN original_size::FLOAT / compressed_size::FLOAT ELSE 1.0 END;

    INSERT INTO compression_metadata (
        memory_id,
        memory_type,
        is_compressed,
        compression_algorithm,
        original_size_bytes,
        compressed_size_bytes,
        compression_ratio,
        compression_time_ms,
        compression_level
    ) VALUES (
        memory_id_param,
        memory_type_param,
        TRUE,
        algorithm,
        original_size,
        compressed_size,
        ratio,
        compression_time_ms,
        level_param
    ) ON CONFLICT (memory_id, memory_type) DO UPDATE
    SET
        is_compressed = TRUE,
        compression_algorithm = algorithm,
        original_size_bytes = original_size,
        compressed_size_bytes = compressed_size,
        compression_ratio = ratio,
        compression_time_ms = compression_time_ms,
        compression_level = level_param,
        updated_at = NOW()
    RETURNING id INTO new_compression_id;

    -- Update tier state
    UPDATE memory_tier_state
    SET
        compression_enabled = TRUE,
        compression_algorithm = algorithm,
        compressed_size_bytes = compressed_size,
        updated_at = NOW()
    WHERE memory_id = memory_id_param AND memory_type = memory_type_param;

    RETURN new_compression_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record prefetch cache entry
CREATE OR REPLACE FUNCTION record_prefetch(
    cache_key_param VARCHAR,
    cache_type_param VARCHAR,
    memory_ids_param UUID[],
    trigger_param VARCHAR,
    confidence_param FLOAT,
    pattern_id_param UUID DEFAULT NULL,
    expires_at_param TIMESTAMP WITH TIME ZONE DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    new_cache_id UUID;
    total_size INTEGER;
BEGIN
    -- Calculate total size
    SELECT COALESCE(SUM(size_bytes), 0) INTO total_size
    FROM memory_tier_state
    WHERE memory_id = ANY(memory_ids_param);

    INSERT INTO prefetch_cache (
        cache_key,
        cache_type,
        memory_ids,
        prefetch_trigger,
        prediction_confidence,
        pattern_id,
        total_size_bytes,
        expires_at
    ) VALUES (
        cache_key_param,
        cache_type_param,
        memory_ids_param,
        trigger_param,
        confidence_param,
        pattern_id_param,
        total_size,
        COALESCE(expires_at_param, NOW() + INTERVAL '1 hour')
    ) ON CONFLICT (cache_key, cache_type) DO UPDATE
    SET
        memory_ids = memory_ids_param,
        prefetch_trigger = trigger_param,
        prediction_confidence = confidence_param,
        pattern_id = pattern_id_param,
        total_size_bytes = total_size,
        expires_at = COALESCE(expires_at_param, NOW() + INTERVAL '1 hour'),
        updated_at = NOW()
    RETURNING id INTO new_cache_id;

    RETURN new_cache_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record cache hit
CREATE OR REPLACE FUNCTION record_cache_hit(cache_id_param UUID)
RETURNS void AS $$
BEGIN
    UPDATE prefetch_cache
    SET
        hit_count = hit_count + 1,
        last_hit_at = NOW(),
        updated_at = NOW()
    WHERE id = cache_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to record cache miss
CREATE OR REPLACE FUNCTION record_cache_miss(cache_id_param UUID)
RETURNS void AS $$
BEGIN
    UPDATE prefetch_cache
    SET
        miss_count = miss_count + 1,
        updated_at = NOW()
    WHERE id = cache_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate access patterns (returns recent access count)
CREATE OR REPLACE FUNCTION get_recent_access_count(
    memory_id_param UUID,
    memory_type_param VARCHAR,
    hours_param INTEGER DEFAULT 24
)
RETURNS INTEGER AS $$
DECLARE
    access_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO access_count
    FROM memory_access_logs
    WHERE memory_id = memory_id_param
      AND memory_type = memory_type_param
      AND access_timestamp >= NOW() - (hours_param || ' hours')::INTERVAL;

    RETURN access_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: Triggers
-- ============================================================================

-- Auto-update timestamps for memory_tier_state
DROP TRIGGER IF EXISTS update_memory_tier_state_timestamp ON memory_tier_state;
CREATE TRIGGER update_memory_tier_state_timestamp
    BEFORE UPDATE ON memory_tier_state
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_optimization_timestamp();

-- Auto-update timestamps for compression_metadata
DROP TRIGGER IF EXISTS update_compression_metadata_timestamp ON compression_metadata;
CREATE TRIGGER update_compression_metadata_timestamp
    BEFORE UPDATE ON compression_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_optimization_timestamp();

-- Auto-update timestamps for prefetch_cache
DROP TRIGGER IF EXISTS update_prefetch_cache_timestamp ON prefetch_cache;
CREATE TRIGGER update_prefetch_cache_timestamp
    BEFORE UPDATE ON prefetch_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_optimization_timestamp();

-- ============================================================================
-- SECTION 8: Views
-- ============================================================================

-- View for memory tier distribution
CREATE OR REPLACE VIEW memory_tier_distribution AS
SELECT
    current_tier,
    COUNT(*) AS memory_count,
    SUM(size_bytes) AS total_bytes,
    AVG(access_frequency) AS avg_access_frequency,
    AVG(recency_score) AS avg_recency_score
FROM memory_tier_state
GROUP BY current_tier;

-- View for hot memory candidates (high access, recent)
CREATE OR REPLACE VIEW hot_memory_candidates AS
SELECT
    mts.*,
    cm.compression_ratio,
    cm.is_compressed
FROM memory_tier_state mts
LEFT JOIN compression_metadata cm ON mts.memory_id = cm.memory_id AND mts.memory_type = cm.memory_type
WHERE mts.current_tier IN ('warm', 'cold')
  AND mts.access_frequency > 1.0  -- More than 1 access per hour
  AND mts.recency_score > 0.7
ORDER BY mts.access_frequency DESC, mts.recency_score DESC;

-- View for cold memory candidates (low access, old)
CREATE OR REPLACE VIEW cold_memory_candidates AS
SELECT
    mts.*,
    cm.compression_ratio
FROM memory_tier_state mts
LEFT JOIN compression_metadata cm ON mts.memory_id = cm.memory_id AND mts.memory_type = cm.memory_type
WHERE mts.current_tier IN ('hot', 'warm')
  AND mts.access_frequency < 0.1  -- Less than 0.1 accesses per hour
  AND mts.recency_score < 0.3
ORDER BY mts.access_frequency ASC, mts.recency_score ASC;

-- View for compression effectiveness
CREATE OR REPLACE VIEW compression_effectiveness AS
SELECT
    compression_algorithm,
    COUNT(*) AS compressed_count,
    AVG(compression_ratio) AS avg_compression_ratio,
    AVG(compression_time_ms) AS avg_compression_time,
    AVG(decompression_time_ms) AS avg_decompression_time,
    SUM(original_size_bytes) AS total_original_bytes,
    SUM(compressed_size_bytes) AS total_compressed_bytes,
    ROUND((100.0 * (1 - SUM(compressed_size_bytes)::NUMERIC / NULLIF(SUM(original_size_bytes), 0)))::NUMERIC, 2) AS space_saved_percent
FROM compression_metadata
WHERE is_compressed = TRUE
GROUP BY compression_algorithm;

-- View for prefetch cache performance
CREATE OR REPLACE VIEW prefetch_cache_performance AS
SELECT
    cache_type,
    COUNT(*) AS entry_count,
    SUM(hit_count) AS total_hits,
    SUM(miss_count) AS total_misses,
    ROUND((100.0 * SUM(hit_count) / NULLIF(SUM(hit_count) + SUM(miss_count), 0))::NUMERIC, 2) AS hit_rate_percent,
    AVG(prediction_confidence) AS avg_confidence,
    SUM(total_size_bytes) AS total_cached_bytes
FROM prefetch_cache
GROUP BY cache_type;

-- View for low performing prefetch entries
CREATE OR REPLACE VIEW low_performing_prefetch AS
SELECT
    *,
    ROUND((100.0 * hit_count / NULLIF(hit_count + miss_count, 0))::NUMERIC, 2) AS hit_rate_percent
FROM prefetch_cache
WHERE hit_count + miss_count > 5
  AND (hit_count::FLOAT / NULLIF(hit_count + miss_count, 0)) < 0.3
ORDER BY hit_count ASC, miss_count DESC;

-- View for recent access patterns (last hour)
CREATE OR REPLACE VIEW recent_access_patterns AS
SELECT
    agent_id,
    access_type,
    COUNT(*) AS access_count,
    AVG(access_duration_ms) AS avg_duration_ms,
    ROUND((100.0 * SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) / COUNT(*))::NUMERIC, 2) AS cache_hit_rate
FROM memory_access_logs
WHERE access_timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY agent_id, access_type;

-- View for memory requiring tier review
CREATE OR REPLACE VIEW memory_requiring_tier_review AS
SELECT * FROM memory_tier_state
WHERE next_review_at IS NOT NULL
  AND next_review_at <= NOW()
ORDER BY next_review_at;

-- ============================================================================
-- SECTION 9: Comments
-- ============================================================================

COMMENT ON TABLE memory_access_logs IS 'Tracks memory access patterns for optimization decisions';
COMMENT ON TABLE memory_tier_state IS 'Current tier classification for memory items with dynamic tiering';
COMMENT ON TABLE compression_metadata IS 'Compression state and statistics for memory items';
COMMENT ON TABLE prefetch_cache IS 'Prefetch cache state and effectiveness tracking';

COMMENT ON COLUMN memory_access_logs.access_type IS 'Type: read, write, update, delete, search';
COMMENT ON COLUMN memory_access_logs.is_sequential IS 'Whether access is part of sequential pattern';
COMMENT ON COLUMN memory_access_logs.pattern_group_id IS 'Groups related accesses for pattern detection';

COMMENT ON COLUMN memory_tier_state.current_tier IS 'Tier: hot, warm, cold, archive';
COMMENT ON COLUMN memory_tier_state.access_frequency IS 'Accesses per hour';
COMMENT ON COLUMN memory_tier_state.tier_algorithm IS 'Algorithm used for tier decision';

COMMENT ON COLUMN compression_metadata.compression_ratio IS 'original_size / compressed_size';
COMMENT ON COLUMN compression_metadata.decompression_count IS 'Number of times decompressed for access';

COMMENT ON COLUMN prefetch_cache.cache_type IS 'Type: prediction, pattern, recent, frequent';
COMMENT ON COLUMN prefetch_cache.prediction_confidence IS 'Confidence in prefetch prediction (0-1)';
COMMENT ON COLUMN prefetch_cache.hit_count IS 'Number of successful cache hits';

-- ============================================================================
-- SECTION 10: Migration Registration
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        INSERT INTO schema_migrations (version, applied_at)
        VALUES ('007', NOW())
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- Tables created:
--   - memory_access_logs (access pattern tracking)
--   - memory_tier_state (tier classification)
--   - compression_metadata (compression tracking)
--   - prefetch_cache (prefetch state)
--
-- Functions created:
--   - update_memory_optimization_timestamp()
--   - log_memory_access()
--   - update_memory_tier()
--   - record_compression()
--   - record_prefetch()
--   - record_cache_hit()
--   - record_cache_miss()
--   - get_recent_access_count()
--
-- Views created:
--   - memory_tier_distribution
--   - hot_memory_candidates
--   - cold_memory_candidates
--   - compression_effectiveness
--   - prefetch_cache_performance
--   - low_performing_prefetch
--   - recent_access_patterns
--   - memory_requiring_tier_review
-- ============================================================================
