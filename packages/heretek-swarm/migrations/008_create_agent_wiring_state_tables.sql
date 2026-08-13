-- Migration: Create agent wiring state tables
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Support agent wiring state tracking including learning status,
--          memory configuration, and consensus participation settings
-- Session: 45 - Database Migrations
--
-- This migration creates tables for:
-- 1. agent_learning_state - Per-agent learning status and capabilities
-- 2. agent_memory_config - Per-agent memory configuration
-- 3. agent_consensus_config - Per-agent consensus participation settings
--
-- All tables are idempotent (CREATE IF NOT EXISTS) and include rollback support

-- ============================================================================
-- SECTION 1: Agent Learning State Table
-- ============================================================================
-- Tracks per-agent learning status, capabilities, and progress.
-- Supports the agent wiring system from Session 44.

CREATE TABLE IF NOT EXISTS agent_learning_state (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(100),

    -- Learning status
    learning_enabled BOOLEAN DEFAULT TRUE,
    learning_state VARCHAR(50) DEFAULT 'active',
    -- States: active, paused, completed, disabled

    -- Learning capabilities
    can_learn BOOLEAN DEFAULT TRUE,
    can_teach BOOLEAN DEFAULT FALSE,
    can_share_knowledge BOOLEAN DEFAULT TRUE,

    -- Learning progress
    lessons_completed INTEGER DEFAULT 0,
    patterns_learned INTEGER DEFAULT 0,
    skills_acquired TEXT[] DEFAULT '{}',

    -- Learning metrics
    learning_rate FLOAT DEFAULT 0.1,
    retention_score FLOAT DEFAULT 0.5,
    adaptation_score FLOAT DEFAULT 0.5,

    -- Knowledge state
    knowledge_domains TEXT[] DEFAULT '{}',
    expertise_levels JSONB DEFAULT '{}',
    -- Map of domain -> expertise level

    -- Learning preferences
    preferred_learning_style VARCHAR(50),
    -- Styles: supervised, unsupervised, reinforcement, collaborative

    learning_goals JSONB DEFAULT '{}',
    -- Structured learning objectives

    -- Session tracking
    current_session_id UUID,
    last_learning_session_at TIMESTAMP WITH TIME ZONE,

    -- Statistics
    total_learning_time_seconds FLOAT DEFAULT 0,
    successful_learnings INTEGER DEFAULT 0,
    failed_learnings INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(agent_id)
);

-- ============================================================================
-- SECTION 2: Agent Memory Configuration Table
-- ============================================================================
-- Stores per-agent memory configuration settings.
-- Enables customized memory behavior per agent.

CREATE TABLE IF NOT EXISTS agent_memory_config (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_id VARCHAR(255) NOT NULL,

    -- Memory capacity
    max_memories INTEGER DEFAULT 1000,
    max_memory_size_bytes BIGINT DEFAULT 104857600, -- 100MB

    -- Tier configuration
    hot_tier_threshold FLOAT DEFAULT 0.8,
    warm_tier_threshold FLOAT DEFAULT 0.5,
    cold_tier_threshold FLOAT DEFAULT 0.2,

    -- Decay configuration
    memory_decay_enabled BOOLEAN DEFAULT TRUE,
    base_decay_rate FLOAT DEFAULT 0.99,
    decay_interval_seconds INTEGER DEFAULT 3600,

    -- Compression configuration
    compression_enabled BOOLEAN DEFAULT TRUE,
    compression_algorithm VARCHAR(50) DEFAULT 'zstd',
    compression_threshold_bytes INTEGER DEFAULT 10240, -- 10KB

    -- Prefetch configuration
    prefetch_enabled BOOLEAN DEFAULT TRUE,
    prefetch_lookahead INTEGER DEFAULT 5,
    prefetch_confidence_threshold FLOAT DEFAULT 0.6,

    -- Vector configuration
    vector_search_enabled BOOLEAN DEFAULT TRUE,
    vector_index_type VARCHAR(50) DEFAULT 'hnsw',
    vector_search_k INTEGER DEFAULT 10,

    -- Retention configuration
    retention_policy VARCHAR(50) DEFAULT 'lru_with_importance',
    auto_cleanup_enabled BOOLEAN DEFAULT TRUE,
    cleanup_interval_seconds INTEGER DEFAULT 86400, -- 24 hours

    -- Memory types enabled
    episodic_enabled BOOLEAN DEFAULT TRUE,
    semantic_enabled BOOLEAN DEFAULT TRUE,
    working_enabled BOOLEAN DEFAULT TRUE,

    -- Access control
    allow_cross_agent_sharing BOOLEAN DEFAULT FALSE,
    require_encryption BOOLEAN DEFAULT FALSE,

    -- Custom settings
    custom_config JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(agent_id)
);

-- ============================================================================
-- SECTION 3: Agent Consensus Configuration Table
-- ============================================================================
-- Stores per-agent consensus participation settings.
-- Controls how agents participate in consensus decisions.

CREATE TABLE IF NOT EXISTS agent_consensus_config (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_id VARCHAR(255) NOT NULL,

    -- Participation settings
    consensus_enabled BOOLEAN DEFAULT TRUE,
    can_propose BOOLEAN DEFAULT TRUE,
    can_vote BOOLEAN DEFAULT TRUE,
    can_deliberate BOOLEAN DEFAULT TRUE,

    -- Voting configuration
    default_vote_weight FLOAT DEFAULT 1.0,
    use_expertise_weighting BOOLEAN DEFAULT TRUE,
    max_vote_weight FLOAT DEFAULT 2.0,
    min_vote_weight FLOAT DEFAULT 0.5,

    -- Deliberation settings
    auto_participate BOOLEAN DEFAULT TRUE,
    min_rounds_to_participate INTEGER DEFAULT 1,
    max_arguments_per_round INTEGER DEFAULT 5,

    -- Proposal settings
    can_create_proposals BOOLEAN DEFAULT TRUE,
    proposal_threshold FLOAT DEFAULT 0.5,
    -- Minimum confidence to create proposal

    max_pending_proposals INTEGER DEFAULT 3,

    -- Domain restrictions
    restricted_domains TEXT[] DEFAULT '{}',
    -- Domains where agent cannot participate

    preferred_domains TEXT[] DEFAULT '{}',
    -- Domains agent prefers to participate in

    -- Behavior configuration
    voting_style VARCHAR(50) DEFAULT 'balanced',
    -- Styles: cautious, balanced, aggressive

    deliberation_style VARCHAR(50) DEFAULT 'collaborative',
    -- Styles: competitive, collaborative, analytical

    -- Quorum settings
    requires_quorum BOOLEAN DEFAULT TRUE,
    quorum_participation_weight FLOAT DEFAULT 1.0,

    -- Notification settings
    notify_on_proposal BOOLEAN DEFAULT TRUE,
    notify_on_vote BOOLEAN DEFAULT FALSE,
    notify_on_consensus BOOLEAN DEFAULT TRUE,

    -- Statistics
    proposals_created INTEGER DEFAULT 0,
    votes_cast INTEGER DEFAULT 0,
    arguments_submitted INTEGER DEFAULT 0,
    consensus_participations INTEGER DEFAULT 0,

    -- Performance metrics
    proposal_success_rate FLOAT DEFAULT 0.0,
    voting_accuracy FLOAT DEFAULT 0.5,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_participation_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint
    UNIQUE(agent_id)
);

-- ============================================================================
-- SECTION 4: Indexes
-- ============================================================================

-- Agent Learning State indexes
CREATE INDEX IF NOT EXISTS idx_agent_learning_state_agent ON agent_learning_state(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_learning_state_type ON agent_learning_state(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_learning_state_status ON agent_learning_state(learning_state);
CREATE INDEX IF NOT EXISTS idx_agent_learning_state_active ON agent_learning_state(last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_learning_state_session ON agent_learning_state(current_session_id);

-- Agent Memory Configuration indexes
CREATE INDEX IF NOT EXISTS idx_agent_memory_config_agent ON agent_memory_config(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_config_compression ON agent_memory_config(compression_enabled);
CREATE INDEX IF NOT EXISTS idx_agent_memory_config_prefetch ON agent_memory_config(prefetch_enabled);

-- Agent Consensus Configuration indexes
CREATE INDEX IF NOT EXISTS idx_agent_consensus_config_agent ON agent_consensus_config(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_consensus_config_enabled ON agent_consensus_config(consensus_enabled);
CREATE INDEX IF NOT EXISTS idx_agent_consensus_config_proposals ON agent_consensus_config(proposals_created DESC);
CREATE INDEX IF NOT EXISTS idx_agent_consensus_config_votes ON agent_consensus_config(votes_cast DESC);
CREATE INDEX IF NOT EXISTS idx_agent_consensus_config_last_participation ON agent_consensus_config(last_participation_at DESC);

-- ============================================================================
-- SECTION 5: Functions
-- ============================================================================

-- Function to update timestamp on row update
CREATE OR REPLACE FUNCTION update_agent_wiring_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to initialize agent learning state
CREATE OR REPLACE FUNCTION initialize_agent_learning(
    agent_id_param VARCHAR,
    agent_name_param VARCHAR,
    agent_type_param VARCHAR DEFAULT NULL,
    learning_enabled_param BOOLEAN DEFAULT TRUE
)
RETURNS UUID AS $$
DECLARE
    new_state_id UUID;
BEGIN
    INSERT INTO agent_learning_state (
        agent_id,
        agent_name,
        agent_type,
        learning_enabled,
        learning_state
    ) VALUES (
        agent_id_param,
        agent_name_param,
        agent_type_param,
        learning_enabled_param,
        CASE WHEN learning_enabled_param THEN 'active' ELSE 'disabled' END
    ) ON CONFLICT (agent_id) DO UPDATE
    SET
        agent_name = agent_name_param,
        agent_type = agent_type_param,
        learning_enabled = learning_enabled_param,
        learning_state = CASE WHEN learning_enabled_param THEN 'active' ELSE 'disabled' END,
        updated_at = NOW()
    RETURNING id INTO new_state_id;

    RETURN new_state_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record learning progress
CREATE OR REPLACE FUNCTION record_learning_progress(
    agent_id_param VARCHAR,
    pattern_learned BOOLEAN DEFAULT FALSE,
    lesson_completed BOOLEAN DEFAULT FALSE,
    skill_acquired VARCHAR DEFAULT NULL,
    learning_time_seconds FLOAT DEFAULT 0,
    success BOOLEAN DEFAULT TRUE
)
RETURNS void AS $$
BEGIN
    UPDATE agent_learning_state
    SET
        patterns_learned = patterns_learned + CASE WHEN pattern_learned THEN 1 ELSE 0 END,
        lessons_completed = lessons_completed + CASE WHEN lesson_completed THEN 1 ELSE 0 END,
        skills_acquired = CASE
            WHEN skill_acquired IS NOT NULL
            THEN array_append(skills_acquired, skill_acquired)
            ELSE skills_acquired
        END,
        total_learning_time_seconds = total_learning_time_seconds + learning_time_seconds,
        successful_learnings = successful_learnings + CASE WHEN success THEN 1 ELSE 0 END,
        failed_learnings = failed_learnings + CASE WHEN NOT success THEN 1 ELSE 0 END,
        last_learning_session_at = NOW(),
        last_active_at = NOW(),
        updated_at = NOW()
    WHERE agent_id = agent_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to update agent memory configuration
CREATE OR REPLACE FUNCTION configure_agent_memory(
    agent_id_param VARCHAR,
    max_memories_param INTEGER DEFAULT NULL,
    compression_enabled_param BOOLEAN DEFAULT NULL,
    prefetch_enabled_param BOOLEAN DEFAULT NULL,
    custom_config_param JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    new_config_id UUID;
BEGIN
    INSERT INTO agent_memory_config (
        agent_id,
        max_memories,
        compression_enabled,
        prefetch_enabled,
        custom_config
    ) VALUES (
        agent_id_param,
        max_memories_param,
        compression_enabled_param,
        prefetch_enabled_param,
        custom_config_param
    ) ON CONFLICT (agent_id) DO UPDATE
    SET
        max_memories = COALESCE(max_memories_param, agent_memory_config.max_memories),
        compression_enabled = COALESCE(compression_enabled_param, agent_memory_config.compression_enabled),
        prefetch_enabled = COALESCE(prefetch_enabled_param, agent_memory_config.prefetch_enabled),
        custom_config = CASE
            WHEN custom_config_param != '{}'::jsonb
            THEN agent_memory_config.custom_config || custom_config_param
            ELSE agent_memory_config.custom_config
        END,
        updated_at = NOW()
    RETURNING id INTO new_config_id;

    RETURN new_config_id;
END;
$$ LANGUAGE plpgsql;

-- Function to configure agent consensus participation
CREATE OR REPLACE FUNCTION configure_agent_consensus(
    agent_id_param VARCHAR,
    consensus_enabled_param BOOLEAN DEFAULT NULL,
    can_propose_param BOOLEAN DEFAULT NULL,
    can_vote_param BOOLEAN DEFAULT NULL,
    use_expertise_weighting_param BOOLEAN DEFAULT NULL,
    preferred_domains_param TEXT[] DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    new_config_id UUID;
BEGIN
    INSERT INTO agent_consensus_config (
        agent_id,
        consensus_enabled,
        can_propose,
        can_vote,
        use_expertise_weighting,
        preferred_domains
    ) VALUES (
        agent_id_param,
        consensus_enabled_param,
        can_propose_param,
        can_vote_param,
        use_expertise_weighting_param,
        preferred_domains_param
    ) ON CONFLICT (agent_id) DO UPDATE
    SET
        consensus_enabled = COALESCE(consensus_enabled_param, agent_consensus_config.consensus_enabled),
        can_propose = COALESCE(can_propose_param, agent_consensus_config.can_propose),
        can_vote = COALESCE(can_vote_param, agent_consensus_config.can_vote),
        use_expertise_weighting = COALESCE(use_expertise_weighting_param, agent_consensus_config.use_expertise_weighting),
        preferred_domains = CASE
            WHEN preferred_domains_param != '{}'
            THEN preferred_domains_param
            ELSE agent_consensus_config.preferred_domains
        END,
        updated_at = NOW()
    RETURNING id INTO new_config_id;

    RETURN new_config_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record consensus participation
CREATE OR REPLACE FUNCTION record_consensus_participation(
    agent_id_param VARCHAR,
    participation_type VARCHAR,
    -- Types: vote, proposal, argument
    success BOOLEAN DEFAULT TRUE
)
RETURNS void AS $$
BEGIN
    UPDATE agent_consensus_config
    SET
        votes_cast = votes_cast + CASE WHEN participation_type = 'vote' THEN 1 ELSE 0 END,
        proposals_created = proposals_created + CASE WHEN participation_type = 'proposal' THEN 1 ELSE 0 END,
        arguments_submitted = arguments_submitted + CASE WHEN participation_type = 'argument' THEN 1 ELSE 0 END,
        consensus_participations = consensus_participations + 1,
        last_participation_at = NOW(),
        updated_at = NOW()
    WHERE agent_id = agent_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to get full agent wiring state
CREATE OR REPLACE FUNCTION get_agent_wiring_state(agent_id_param VARCHAR)
RETURNS TABLE (
    learning_state JSONB,
    memory_config JSONB,
    consensus_config JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        to_jsonb(als) AS learning_state,
        to_jsonb(amc) AS memory_config,
        to_jsonb(acc) AS consensus_config
    FROM agent_learning_state als
    LEFT JOIN agent_memory_config amc ON als.agent_id = amc.agent_id
    LEFT JOIN agent_consensus_config acc ON als.agent_id = acc.agent_id
    WHERE als.agent_id = agent_id_param;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 6: Triggers
-- ============================================================================

-- Auto-update timestamps for agent_learning_state
DROP TRIGGER IF EXISTS update_agent_learning_state_timestamp ON agent_learning_state;
CREATE TRIGGER update_agent_learning_state_timestamp
    BEFORE UPDATE ON agent_learning_state
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_wiring_timestamp();

-- Auto-update timestamps for agent_memory_config
DROP TRIGGER IF EXISTS update_agent_memory_config_timestamp ON agent_memory_config;
CREATE TRIGGER update_agent_memory_config_timestamp
    BEFORE UPDATE ON agent_memory_config
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_wiring_timestamp();

-- Auto-update timestamps for agent_consensus_config
DROP TRIGGER IF EXISTS update_agent_consensus_config_timestamp ON agent_consensus_config;
CREATE TRIGGER update_agent_consensus_config_timestamp
    BEFORE UPDATE ON agent_consensus_config
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_wiring_timestamp();

-- ============================================================================
-- SECTION 7: Views
-- ============================================================================

-- View for active learning agents
CREATE OR REPLACE VIEW active_learning_agents AS
SELECT
    agent_id,
    agent_name,
    agent_type,
    learning_state,
    lessons_completed,
    patterns_learned,
    skills_acquired,
    learning_rate,
    retention_score,
    last_learning_session_at,
    last_active_at
FROM agent_learning_state
WHERE learning_enabled = TRUE
  AND learning_state = 'active'
ORDER BY last_active_at DESC;

-- View for agent learning summary
CREATE OR REPLACE VIEW agent_learning_summary AS
SELECT
    agent_type,
    COUNT(*) AS agent_count,
    AVG(lessons_completed) AS avg_lessons,
    AVG(patterns_learned) AS avg_patterns,
    AVG(retention_score) AS avg_retention,
    AVG(adaptation_score) AS avg_adaptation,
    SUM(total_learning_time_seconds) AS total_learning_time
FROM agent_learning_state
WHERE learning_enabled = TRUE
GROUP BY agent_type;

-- View for agents with custom memory config
CREATE OR REPLACE VIEW custom_memory_agents AS
SELECT
    amc.agent_id,
    als.agent_name,
    amc.max_memories,
    amc.compression_enabled,
    amc.prefetch_enabled,
    amc.retention_policy,
    amc.custom_config
FROM agent_memory_config amc
JOIN agent_learning_state als ON amc.agent_id = als.agent_id
WHERE amc.custom_config != '{}'::jsonb
   OR amc.max_memories != 1000
   OR amc.compression_enabled != TRUE
ORDER BY amc.agent_id;

-- View for active consensus participants
CREATE OR REPLACE VIEW active_consensus_participants AS
SELECT
    acc.agent_id,
    als.agent_name,
    acc.consensus_enabled,
    acc.can_propose,
    acc.can_vote,
    acc.proposals_created,
    acc.votes_cast,
    acc.arguments_submitted,
    acc.last_participation_at,
    acc.voting_style,
    acc.deliberation_style
FROM agent_consensus_config acc
JOIN agent_learning_state als ON acc.agent_id = als.agent_id
WHERE acc.consensus_enabled = TRUE
ORDER BY acc.votes_cast DESC, acc.proposals_created DESC;

-- View for consensus participation statistics
CREATE OR REPLACE VIEW consensus_participation_stats AS
SELECT
    COUNT(*) FILTER (WHERE consensus_enabled = TRUE) AS enabled_agents,
    COUNT(*) FILTER (WHERE can_propose = TRUE) AS can_propose_count,
    COUNT(*) FILTER (WHERE can_vote = TRUE) AS can_vote_count,
    SUM(proposals_created) AS total_proposals,
    SUM(votes_cast) AS total_votes,
    SUM(arguments_submitted) AS total_arguments,
    AVG(proposal_success_rate) AS avg_proposal_success,
    AVG(voting_accuracy) AS avg_voting_accuracy
FROM agent_consensus_config;

-- View for agents needing attention
-- Migration 002 defines a view of the same name with a different column set
-- (SELECT * FROM agent_states). CREATE OR REPLACE VIEW cannot change an
-- existing view's columns, so drop the old definition before recreating it
-- with the richer learning/consensus columns below.
DROP VIEW IF EXISTS agents_needing_attention;
CREATE VIEW agents_needing_attention AS
SELECT
    als.agent_id,
    als.agent_name,
    als.learning_state,
    CASE
        WHEN als.learning_state = 'disabled' THEN 'learning_disabled'
        WHEN als.failed_learnings > als.successful_learnings * 2 THEN 'high_failure_rate'
        WHEN als.retention_score < 0.3 THEN 'low_retention'
        ELSE NULL
    END AS attention_reason,
    acc.consensus_enabled,
    CASE
        WHEN NOT acc.consensus_enabled THEN 'consensus_disabled'
        WHEN acc.voting_accuracy < 0.3 THEN 'low_voting_accuracy'
        ELSE NULL
    END AS consensus_issue
FROM agent_learning_state als
JOIN agent_consensus_config acc ON als.agent_id = acc.agent_id
WHERE als.learning_state != 'active'
   OR als.failed_learnings > als.successful_learnings * 2
   OR als.retention_score < 0.3
   OR NOT acc.consensus_enabled
   OR acc.voting_accuracy < 0.3
ORDER BY als.agent_id;

-- ============================================================================
-- SECTION 8: Comments
-- ============================================================================

COMMENT ON TABLE agent_learning_state IS 'Per-agent learning status, capabilities, and progress tracking';
COMMENT ON TABLE agent_memory_config IS 'Per-agent memory configuration settings for customized behavior';
COMMENT ON TABLE agent_consensus_config IS 'Per-agent consensus participation settings and statistics';

COMMENT ON COLUMN agent_learning_state.learning_state IS 'State: active, paused, completed, disabled';
COMMENT ON COLUMN agent_learning_state.preferred_learning_style IS 'Style: supervised, unsupervised, reinforcement, collaborative';
COMMENT ON COLUMN agent_learning_state.expertise_levels IS 'JSONB map of domain -> expertise level';

COMMENT ON COLUMN agent_memory_config.hot_tier_threshold IS 'Threshold for hot tier classification (0-1)';
COMMENT ON COLUMN agent_memory_config.retention_policy IS 'Policy: lru_with_importance, fifo, lfu, custom';

COMMENT ON COLUMN agent_consensus_config.voting_style IS 'Style: cautious, balanced, aggressive';
COMMENT ON COLUMN agent_consensus_config.deliberation_style IS 'Style: competitive, collaborative, analytical';
COMMENT ON COLUMN agent_consensus_config.restricted_domains IS 'Domains where agent cannot participate in consensus';

-- ============================================================================
-- SECTION 9: Migration Registration
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        INSERT INTO schema_migrations (version, applied_at)
        VALUES ('008', NOW())
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- Tables created:
--   - agent_learning_state (learning status and capabilities)
--   - agent_memory_config (memory configuration)
--   - agent_consensus_config (consensus participation)
--
-- Functions created:
--   - update_agent_wiring_timestamp()
--   - initialize_agent_learning()
--   - record_learning_progress()
--   - configure_agent_memory()
--   - configure_agent_consensus()
--   - record_consensus_participation()
--   - get_agent_wiring_state()
--
-- Views created:
--   - active_learning_agents
--   - agent_learning_summary
--   - custom_memory_agents
--   - active_consensus_participants
--   - consensus_participation_stats
--   - agents_needing_attention
-- ============================================================================
