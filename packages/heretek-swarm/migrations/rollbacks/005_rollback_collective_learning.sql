-- Rollback: 005_create_collective_learning_tables.sql
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Rollback migration 005 - Collective Learning Tables
--
-- WARNING: This will permanently delete all data in the affected tables!
-- Make sure to backup any important data before running this rollback.
--
-- Tables dropped:
--   - pattern_subscriptions
--   - knowledge_transformations
--   - collective_patterns
--
-- Functions dropped:
--   - update_collective_learning_timestamp()
--   - increment_pattern_usage()
--   - validate_pattern()
--   - record_transformation_chain()
--
-- Views dropped:
--   - validated_patterns
--   - active_pattern_subscriptions
--   - transformation_chains
--   - high_impact_transformations

-- ============================================================================
-- SECTION 1: Drop Views
-- ============================================================================

DROP VIEW IF EXISTS high_impact_transformations CASCADE;
DROP VIEW IF EXISTS transformation_chains CASCADE;
DROP VIEW IF EXISTS active_pattern_subscriptions CASCADE;
DROP VIEW IF EXISTS validated_patterns CASCADE;

-- ============================================================================
-- SECTION 2: Drop Triggers
-- ============================================================================

DROP TRIGGER IF EXISTS update_pattern_subscriptions_timestamp ON pattern_subscriptions;
DROP TRIGGER IF EXISTS update_knowledge_transformations_timestamp ON knowledge_transformations;
DROP TRIGGER IF EXISTS update_collective_patterns_timestamp ON collective_patterns;

-- ============================================================================
-- SECTION 3: Drop Functions
-- ============================================================================

DROP FUNCTION IF EXISTS record_transformation_chain(UUID, VARCHAR, UUID, VARCHAR, VARCHAR, VARCHAR, JSONB);
DROP FUNCTION IF EXISTS validate_pattern(UUID, VARCHAR);
DROP FUNCTION IF EXISTS increment_pattern_usage(UUID);
DROP FUNCTION IF EXISTS update_collective_learning_timestamp();

-- ============================================================================
-- SECTION 4: Drop Indexes
-- ============================================================================

-- Pattern Subscriptions indexes
DROP INDEX IF EXISTS idx_pattern_subscriptions_created;
DROP INDEX IF EXISTS idx_pattern_subscriptions_type;
DROP INDEX IF EXISTS idx_pattern_subscriptions_agent;
DROP INDEX IF EXISTS idx_pattern_subscriptions_pattern;

-- Knowledge Transformations indexes
DROP INDEX IF EXISTS idx_knowledge_transformations_created;
DROP INDEX IF EXISTS idx_knowledge_transformations_quality;
DROP INDEX IF EXISTS idx_knowledge_transformations_agent;
DROP INDEX IF EXISTS idx_knowledge_transformations_target;
DROP INDEX IF EXISTS idx_knowledge_transformations_source;
DROP INDEX IF EXISTS idx_knowledge_transformations_type;

-- Collective Patterns indexes
DROP INDEX IF EXISTS idx_collective_patterns_type_state;
DROP INDEX IF EXISTS idx_collective_patterns_parent;
DROP INDEX IF EXISTS idx_collective_patterns_discovered_by;
DROP INDEX IF EXISTS idx_collective_patterns_created;
DROP INDEX IF EXISTS idx_collective_patterns_confidence;
DROP INDEX IF EXISTS idx_collective_patterns_state;
DROP INDEX IF EXISTS idx_collective_patterns_category;
DROP INDEX IF EXISTS idx_collective_patterns_type;

-- ============================================================================
-- SECTION 5: Drop Tables
-- ============================================================================

DROP TABLE IF EXISTS pattern_subscriptions CASCADE;
DROP TABLE IF EXISTS knowledge_transformations CASCADE;
DROP TABLE IF EXISTS collective_patterns CASCADE;

-- ============================================================================
-- SECTION 6: Remove Migration Record
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        DELETE FROM schema_migrations WHERE version = '005';
    END IF;
END $$;

-- ============================================================================
-- Rollback Complete
-- ============================================================================
-- All tables, functions, views, and indexes from migration 005 have been dropped.
-- Data has been permanently deleted.
-- ============================================================================
