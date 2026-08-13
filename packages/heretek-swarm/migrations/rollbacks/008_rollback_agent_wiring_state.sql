-- Rollback: 008_create_agent_wiring_state_tables.sql
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Rollback migration 008 - Agent Wiring State Tables
--
-- WARNING: This will permanently delete all data in the affected tables!
-- Make sure to backup any important data before running this rollback.
--
-- Tables dropped:
--   - agent_consensus_config
--   - agent_memory_config
--   - agent_learning_state
--
-- Functions dropped:
--   - update_agent_wiring_timestamp()
--   - initialize_agent_learning()
--   - record_learning_progress()
--   - configure_agent_memory()
--   - configure_agent_consensus()
--   - record_consensus_participation()
--   - get_agent_wiring_state()
--
-- Views dropped:
--   - agents_needing_attention
--   - consensus_participation_stats
--   - active_consensus_participants
--   - custom_memory_agents
--   - agent_learning_summary
--   - active_learning_agents

-- ============================================================================
-- SECTION 1: Drop Views
-- ============================================================================

DROP VIEW IF EXISTS agents_needing_attention CASCADE;
DROP VIEW IF EXISTS consensus_participation_stats CASCADE;
DROP VIEW IF EXISTS active_consensus_participants CASCADE;
DROP VIEW IF EXISTS custom_memory_agents CASCADE;
DROP VIEW IF EXISTS agent_learning_summary CASCADE;
DROP VIEW IF EXISTS active_learning_agents CASCADE;

-- ============================================================================
-- SECTION 2: Drop Triggers
-- ============================================================================

DROP TRIGGER IF EXISTS update_agent_consensus_config_timestamp ON agent_consensus_config;
DROP TRIGGER IF EXISTS update_agent_memory_config_timestamp ON agent_memory_config;
DROP TRIGGER IF EXISTS update_agent_learning_state_timestamp ON agent_learning_state;

-- ============================================================================
-- SECTION 3: Drop Functions
-- ============================================================================

DROP FUNCTION IF EXISTS get_agent_wiring_state(VARCHAR);
DROP FUNCTION IF EXISTS record_consensus_participation(VARCHAR, VARCHAR, BOOLEAN);
DROP FUNCTION IF EXISTS configure_agent_consensus(VARCHAR, BOOLEAN, BOOLEAN, BOOLEAN, BOOLEAN, TEXT[]);
DROP FUNCTION IF EXISTS configure_agent_memory(VARCHAR, INTEGER, BOOLEAN, BOOLEAN, JSONB);
DROP FUNCTION IF EXISTS record_learning_progress(VARCHAR, BOOLEAN, BOOLEAN, VARCHAR, FLOAT, BOOLEAN);
DROP FUNCTION IF EXISTS initialize_agent_learning(VARCHAR, VARCHAR, VARCHAR, BOOLEAN);
DROP FUNCTION IF EXISTS update_agent_wiring_timestamp();

-- ============================================================================
-- SECTION 4: Drop Indexes
-- ============================================================================

-- Agent Consensus Configuration indexes
DROP INDEX IF EXISTS idx_agent_consensus_config_last_participation;
DROP INDEX IF EXISTS idx_agent_consensus_config_votes;
DROP INDEX IF EXISTS idx_agent_consensus_config_proposals;
DROP INDEX IF EXISTS idx_agent_consensus_config_enabled;
DROP INDEX IF EXISTS idx_agent_consensus_config_agent;

-- Agent Memory Configuration indexes
DROP INDEX IF EXISTS idx_agent_memory_config_prefetch;
DROP INDEX IF EXISTS idx_agent_memory_config_compression;
DROP INDEX IF EXISTS idx_agent_memory_config_agent;

-- Agent Learning State indexes
DROP INDEX IF EXISTS idx_agent_learning_state_session;
DROP INDEX IF EXISTS idx_agent_learning_state_active;
DROP INDEX IF EXISTS idx_agent_learning_state_status;
DROP INDEX IF EXISTS idx_agent_learning_state_type;
DROP INDEX IF EXISTS idx_agent_learning_state_agent;

-- ============================================================================
-- SECTION 5: Drop Tables
-- ============================================================================

DROP TABLE IF EXISTS agent_consensus_config CASCADE;
DROP TABLE IF EXISTS agent_memory_config CASCADE;
DROP TABLE IF EXISTS agent_learning_state CASCADE;

-- ============================================================================
-- SECTION 6: Remove Migration Record
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        DELETE FROM schema_migrations WHERE version = '008';
    END IF;
END $$;

-- ============================================================================
-- Rollback Complete
-- ============================================================================
-- All tables, functions, views, and indexes from migration 008 have been dropped.
-- Data has been permanently deleted.
-- ============================================================================
