-- Rollback: 006_create_consensus_enhancement_tables.sql
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Rollback migration 006 - Consensus Enhancement Tables
--
-- WARNING: This will permanently delete all data in the affected tables!
-- Make sure to backup any important data before running this rollback.
--
-- Tables dropped:
--   - consensus_audit_trail
--   - agent_expertise_profiles
--   - deliberation_arguments
--   - deliberation_rounds
--
-- Functions dropped:
--   - update_consensus_enhancement_timestamp()
--   - start_deliberation_round()
--   - complete_deliberation_round()
--   - record_deliberation_argument()
--   - update_agent_expertise()
--   - record_consensus_event()
--
-- Views dropped:
--   - consensus_full_audit
--   - argument_quality_analysis
--   - proposal_deliberation_history
--   - domain_experts
--   - agent_expertise_summary
--   - active_deliberation_rounds

-- ============================================================================
-- SECTION 1: Drop Views
-- ============================================================================

DROP VIEW IF EXISTS consensus_full_audit CASCADE;
DROP VIEW IF EXISTS argument_quality_analysis CASCADE;
DROP VIEW IF EXISTS proposal_deliberation_history CASCADE;
DROP VIEW IF EXISTS domain_experts CASCADE;
DROP VIEW IF EXISTS agent_expertise_summary CASCADE;
DROP VIEW IF EXISTS active_deliberation_rounds CASCADE;

-- ============================================================================
-- SECTION 2: Drop Triggers
-- ============================================================================

DROP TRIGGER IF EXISTS update_agent_expertise_profiles_timestamp ON agent_expertise_profiles;
DROP TRIGGER IF EXISTS update_deliberation_arguments_timestamp ON deliberation_arguments;
DROP TRIGGER IF EXISTS update_deliberation_rounds_timestamp ON deliberation_rounds;

-- ============================================================================
-- SECTION 3: Drop Functions
-- ============================================================================

DROP FUNCTION IF EXISTS record_consensus_event(VARCHAR, UUID, UUID, UUID, UUID, VARCHAR, TEXT, JSONB);
DROP FUNCTION IF EXISTS update_agent_expertise(VARCHAR, VARCHAR, VARCHAR, VARCHAR, BOOLEAN);
DROP FUNCTION IF EXISTS record_deliberation_argument(UUID, UUID, VARCHAR, TEXT, VARCHAR, UUID);
DROP FUNCTION IF EXISTS complete_deliberation_round(UUID, BOOLEAN, FLOAT, TEXT);
DROP FUNCTION IF EXISTS start_deliberation_round(UUID, VARCHAR, INTEGER);
DROP FUNCTION IF EXISTS update_consensus_enhancement_timestamp();

-- ============================================================================
-- SECTION 4: Drop Indexes
-- ============================================================================

-- Consensus Audit Trail indexes
DROP INDEX IF EXISTS idx_consensus_audit_event_proposal;
DROP INDEX IF EXISTS idx_consensus_audit_occurred;
DROP INDEX IF EXISTS idx_consensus_audit_actor;
DROP INDEX IF EXISTS idx_consensus_audit_round;
DROP INDEX IF EXISTS idx_consensus_audit_proposal;
DROP INDEX IF EXISTS idx_consensus_audit_event_type;

-- Agent Expertise Profiles indexes
DROP INDEX IF EXISTS idx_agent_expertise_domain_subdomain;
DROP INDEX IF EXISTS idx_agent_expertise_active;
DROP INDEX IF EXISTS idx_agent_expertise_score;
DROP INDEX IF EXISTS idx_agent_expertise_domain;
DROP INDEX IF EXISTS idx_agent_expertise_agent;

-- Deliberation Arguments indexes
DROP INDEX IF EXISTS idx_deliberation_arguments_created;
DROP INDEX IF EXISTS idx_deliberation_arguments_quality;
DROP INDEX IF EXISTS idx_deliberation_arguments_parent;
DROP INDEX IF EXISTS idx_deliberation_arguments_agent;
DROP INDEX IF EXISTS idx_deliberation_arguments_type;
DROP INDEX IF EXISTS idx_deliberation_arguments_proposal;
DROP INDEX IF EXISTS idx_deliberation_arguments_round;

-- Deliberation Rounds indexes
DROP INDEX IF EXISTS idx_deliberation_rounds_proposal_round;
DROP INDEX IF EXISTS idx_deliberation_rounds_started;
DROP INDEX IF EXISTS idx_deliberation_rounds_type;
DROP INDEX IF EXISTS idx_deliberation_rounds_state;
DROP INDEX IF EXISTS idx_deliberation_rounds_proposal;

-- ============================================================================
-- SECTION 5: Drop Tables
-- ============================================================================

DROP TABLE IF EXISTS consensus_audit_trail CASCADE;
DROP TABLE IF EXISTS agent_expertise_profiles CASCADE;
DROP TABLE IF EXISTS deliberation_arguments CASCADE;
DROP TABLE IF EXISTS deliberation_rounds CASCADE;

-- ============================================================================
-- SECTION 6: Remove Migration Record
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        DELETE FROM schema_migrations WHERE version = '006';
    END IF;
END $$;

-- ============================================================================
-- Rollback Complete
-- ============================================================================
-- All tables, functions, views, and indexes from migration 006 have been dropped.
-- Data has been permanently deleted.
-- ============================================================================
