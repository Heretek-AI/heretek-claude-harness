-- Rollback: 007_create_memory_optimization_tables.sql
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Rollback migration 007 - Memory Optimization Tables
--
-- WARNING: This will permanently delete all data in the affected tables!
-- Make sure to backup any important data before running this rollback.
--
-- Tables dropped:
--   - prefetch_cache
--   - compression_metadata
--   - memory_tier_state
--   - memory_access_logs
--
-- Functions dropped:
--   - update_memory_optimization_timestamp()
--   - log_memory_access()
--   - update_memory_tier()
--   - record_compression()
--   - record_prefetch()
--   - record_cache_hit()
--   - record_cache_miss()
--   - get_recent_access_count()
--
-- Views dropped:
--   - memory_requiring_tier_review
--   - recent_access_patterns
--   - low_performing_prefetch
--   - prefetch_cache_performance
--   - compression_effectiveness
--   - cold_memory_candidates
--   - hot_memory_candidates
--   - memory_tier_distribution

-- ============================================================================
-- SECTION 1: Drop Views
-- ============================================================================

DROP VIEW IF EXISTS memory_requiring_tier_review CASCADE;
DROP VIEW IF EXISTS recent_access_patterns CASCADE;
DROP VIEW IF EXISTS low_performing_prefetch CASCADE;
DROP VIEW IF EXISTS prefetch_cache_performance CASCADE;
DROP VIEW IF EXISTS compression_effectiveness CASCADE;
DROP VIEW IF EXISTS cold_memory_candidates CASCADE;
DROP VIEW IF EXISTS hot_memory_candidates CASCADE;
DROP VIEW IF EXISTS memory_tier_distribution CASCADE;

-- ============================================================================
-- SECTION 2: Drop Triggers
-- ============================================================================

DROP TRIGGER IF EXISTS update_prefetch_cache_timestamp ON prefetch_cache;
DROP TRIGGER IF EXISTS update_compression_metadata_timestamp ON compression_metadata;
DROP TRIGGER IF EXISTS update_memory_tier_state_timestamp ON memory_tier_state;

-- ============================================================================
-- SECTION 3: Drop Functions
-- ============================================================================

DROP FUNCTION IF EXISTS get_recent_access_count(UUID, VARCHAR, INTEGER);
DROP FUNCTION IF EXISTS record_cache_miss(UUID);
DROP FUNCTION IF EXISTS record_cache_hit(UUID);
DROP FUNCTION IF EXISTS record_prefetch(VARCHAR, VARCHAR, UUID[], VARCHAR, FLOAT, UUID, TIMESTAMP WITH TIME ZONE);
DROP FUNCTION IF EXISTS record_compression(UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, FLOAT, INTEGER);
DROP FUNCTION IF EXISTS update_memory_tier(UUID, VARCHAR, VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS log_memory_access(UUID, VARCHAR, VARCHAR, VARCHAR, UUID, FLOAT, BOOLEAN, VARCHAR);
DROP FUNCTION IF EXISTS update_memory_optimization_timestamp();

-- ============================================================================
-- SECTION 4: Drop Indexes
-- ============================================================================

-- Prefetch Cache indexes
DROP INDEX IF EXISTS idx_prefetch_cache_hits;
DROP INDEX IF EXISTS idx_prefetch_cache_expires;
DROP INDEX IF EXISTS idx_prefetch_cache_state;
DROP INDEX IF EXISTS idx_prefetch_cache_type;
DROP INDEX IF EXISTS idx_prefetch_cache_pattern;
DROP INDEX IF EXISTS idx_prefetch_cache_key;

-- Compression Metadata indexes
DROP INDEX IF EXISTS idx_compression_metadata_compressed;
DROP INDEX IF EXISTS idx_compression_metadata_ratio;
DROP INDEX IF EXISTS idx_compression_metadata_algorithm;
DROP INDEX IF EXISTS idx_compression_metadata_memory;

-- Memory Tier State indexes
DROP INDEX IF EXISTS idx_memory_tier_state_compressed;
DROP INDEX IF EXISTS idx_memory_tier_state_review;
DROP INDEX IF EXISTS idx_memory_tier_state_recency;
DROP INDEX IF EXISTS idx_memory_tier_state_frequency;
DROP INDEX IF EXISTS idx_memory_tier_state_tier;
DROP INDEX IF EXISTS idx_memory_tier_state_memory;

-- Memory Access Logs indexes
DROP INDEX IF EXISTS idx_memory_access_logs_agent_timestamp;
DROP INDEX IF EXISTS idx_memory_access_logs_pattern_group;
DROP INDEX IF EXISTS idx_memory_access_logs_tier;
DROP INDEX IF EXISTS idx_memory_access_logs_cache_hit;
DROP INDEX IF EXISTS idx_memory_access_logs_timestamp;
DROP INDEX IF EXISTS idx_memory_access_logs_type;
DROP INDEX IF EXISTS idx_memory_access_logs_session;
DROP INDEX IF EXISTS idx_memory_access_logs_agent;
DROP INDEX IF EXISTS idx_memory_access_logs_memory;

-- ============================================================================
-- SECTION 5: Drop Tables
-- ============================================================================

DROP TABLE IF EXISTS prefetch_cache CASCADE;
DROP TABLE IF EXISTS compression_metadata CASCADE;
DROP TABLE IF EXISTS memory_tier_state CASCADE;
DROP TABLE IF EXISTS memory_access_logs CASCADE;

-- ============================================================================
-- SECTION 6: Remove Migration Record
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        DELETE FROM schema_migrations WHERE version = '007';
    END IF;
END $$;

-- ============================================================================
-- Rollback Complete
-- ============================================================================
-- All tables, functions, views, and indexes from migration 007 have been dropped.
-- Data has been permanently deleted.
-- ============================================================================
