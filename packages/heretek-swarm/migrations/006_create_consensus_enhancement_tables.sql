-- Migration: Create consensus enhancement tables
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Support enhanced consensus mechanisms with multi-round deliberation,
--          argument exchange, dynamic expertise scoring, and audit trails
-- Session: 45 - Database Migrations
--
-- This migration creates tables for:
-- 1. deliberation_rounds - Multi-round voting records for complex decisions
-- 2. deliberation_arguments - Argument exchange logs during deliberation
-- 3. agent_expertise_profiles - Dynamic expertise scoring for weighted voting
-- 4. consensus_audit_trail - Complete decision history for compliance
--
-- All tables are idempotent (CREATE IF NOT EXISTS) and include rollback support

-- ============================================================================
-- SECTION 1: Deliberation Rounds Table
-- ============================================================================
-- Tracks multi-round deliberation processes for complex consensus decisions.
-- Each proposal can have multiple rounds of voting with evolving positions.

CREATE TABLE IF NOT EXISTS deliberation_rounds (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to consensus proposal (from migration 004)
    proposal_id UUID NOT NULL REFERENCES consensus_proposals(id) ON DELETE CASCADE,

    -- Round identification
    round_number INTEGER NOT NULL DEFAULT 1,
    round_type VARCHAR(50) NOT NULL DEFAULT 'voting',
    -- Types: voting, discussion, refinement, final

    -- Round state
    state VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- States: pending, active, completed, cancelled

    -- Round parameters
    voting_timeout_seconds INTEGER DEFAULT 120,
    min_participants INTEGER DEFAULT 1,

    -- Round results
    votes_cast INTEGER DEFAULT 0,
    votes_for INTEGER DEFAULT 0,
    votes_against INTEGER DEFAULT 0,
    votes_abstain INTEGER DEFAULT 0,
    consensus_reached BOOLEAN DEFAULT FALSE,
    consensus_score FLOAT DEFAULT 0.0,

    -- Round context
    round_summary TEXT,
    round_data JSONB DEFAULT '{}',

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint: one round number per proposal
    UNIQUE(proposal_id, round_number)
);

-- ============================================================================
-- SECTION 2: Deliberation Arguments Table
-- ============================================================================
-- Stores arguments exchanged during deliberation rounds.
-- Enables structured debate and reasoning tracking.

CREATE TABLE IF NOT EXISTS deliberation_arguments (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    deliberation_round_id UUID NOT NULL REFERENCES deliberation_rounds(id) ON DELETE CASCADE,
    proposal_id UUID NOT NULL REFERENCES consensus_proposals(id) ON DELETE CASCADE,

    -- Argument identity
    argument_type VARCHAR(50) NOT NULL,
    -- Types: proposal, support, oppose, question, clarification, amendment

    -- Argument content
    argument_text TEXT NOT NULL,
    argument_data JSONB DEFAULT '{}',

    -- Agent info
    agent_id VARCHAR(255) NOT NULL,
    agent_role VARCHAR(100),

    -- Argument relationships
    parent_argument_id UUID REFERENCES deliberation_arguments(id) ON DELETE SET NULL,
    -- For threading replies to arguments

    -- Argument evaluation
    quality_score FLOAT DEFAULT 0.5,
    relevance_score FLOAT DEFAULT 0.5,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,

    -- Impact on voting
    influenced_votes INTEGER DEFAULT 0,
    -- Count of votes that changed after this argument

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: Agent Expertise Profiles Table
-- ============================================================================
-- Dynamic expertise scoring for weighted voting in consensus.
-- Tracks agent expertise across domains and updates based on performance.

CREATE TABLE IF NOT EXISTS agent_expertise_profiles (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,

    -- Expertise domains
    domain VARCHAR(100) NOT NULL,
    subdomain VARCHAR(100),

    -- Expertise scoring
    expertise_score FLOAT NOT NULL DEFAULT 0.5,
    -- 0-1 score representing agent expertise in this domain

    confidence_level FLOAT DEFAULT 0.5,
    -- Confidence in the expertise score itself

    experience_count INTEGER DEFAULT 0,
    -- Number of decisions participated in this domain

    success_count INTEGER DEFAULT 0,
    -- Number of successful outcomes

    -- Expertise sources
    self_declared BOOLEAN DEFAULT FALSE,
    peer_endorsed BOOLEAN DEFAULT FALSE,
    system_calculated BOOLEAN DEFAULT TRUE,

    -- Endorsements
    endorsements TEXT[] DEFAULT '{}',
    -- List of agents who endorsed this expertise

    -- Voting weight modifier
    voting_weight_modifier FLOAT DEFAULT 1.0,
    -- Multiplier applied to vote weight in this domain

    -- Decay and freshness
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    decay_rate FLOAT DEFAULT 0.99,
    -- Monthly decay rate for expertise score

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint
    UNIQUE(agent_id, domain, subdomain)
);

-- ============================================================================
-- SECTION 4: Consensus Audit Trail Table
-- ============================================================================
-- Complete audit trail for consensus decisions.
-- Provides compliance, debugging, and historical analysis.

CREATE TABLE IF NOT EXISTS consensus_audit_trail (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identification
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    -- Types: proposal_created, vote_cast, round_started, round_completed,
    --        argument_submitted, consensus_reached, consensus_failed,
    --        expertise_updated, proposal_resolved

    -- Event context
    proposal_id UUID REFERENCES consensus_proposals(id) ON DELETE SET NULL,
    deliberation_round_id UUID REFERENCES deliberation_rounds(id) ON DELETE SET NULL,
    vote_id UUID REFERENCES consensus_votes(id) ON DELETE SET NULL,
    argument_id UUID REFERENCES deliberation_arguments(id) ON DELETE SET NULL,

    -- Event actor
    actor_agent VARCHAR(255),
    actor_role VARCHAR(100),

    -- Event details
    event_data JSONB NOT NULL DEFAULT '{}',
    event_description TEXT,

    -- State snapshots
    state_before JSONB,
    state_after JSONB,

    -- Verification
    signature_hash VARCHAR(255),
    -- Hash for integrity verification

    -- Timestamps
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- SECTION 5: Indexes
-- ============================================================================

-- Deliberation Rounds indexes
CREATE INDEX IF NOT EXISTS idx_deliberation_rounds_proposal ON deliberation_rounds(proposal_id);
CREATE INDEX IF NOT EXISTS idx_deliberation_rounds_state ON deliberation_rounds(state);
CREATE INDEX IF NOT EXISTS idx_deliberation_rounds_type ON deliberation_rounds(round_type);
CREATE INDEX IF NOT EXISTS idx_deliberation_rounds_started ON deliberation_rounds(started_at DESC);

-- Composite index for proposal rounds
CREATE INDEX IF NOT EXISTS idx_deliberation_rounds_proposal_round ON deliberation_rounds(proposal_id, round_number);

-- Deliberation Arguments indexes
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_round ON deliberation_arguments(deliberation_round_id);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_proposal ON deliberation_arguments(proposal_id);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_type ON deliberation_arguments(argument_type);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_agent ON deliberation_arguments(agent_id);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_parent ON deliberation_arguments(parent_argument_id);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_quality ON deliberation_arguments(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_deliberation_arguments_created ON deliberation_arguments(created_at DESC);

-- Agent Expertise Profiles indexes
CREATE INDEX IF NOT EXISTS idx_agent_expertise_agent ON agent_expertise_profiles(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_expertise_domain ON agent_expertise_profiles(domain);
CREATE INDEX IF NOT EXISTS idx_agent_expertise_score ON agent_expertise_profiles(expertise_score DESC);
CREATE INDEX IF NOT EXISTS idx_agent_expertise_active ON agent_expertise_profiles(last_active_at DESC);

-- Composite index for domain lookup
CREATE INDEX IF NOT EXISTS idx_agent_expertise_domain_subdomain ON agent_expertise_profiles(domain, subdomain);

-- Consensus Audit Trail indexes
CREATE INDEX IF NOT EXISTS idx_consensus_audit_event_type ON consensus_audit_trail(event_type);
CREATE INDEX IF NOT EXISTS idx_consensus_audit_proposal ON consensus_audit_trail(proposal_id);
CREATE INDEX IF NOT EXISTS idx_consensus_audit_round ON consensus_audit_trail(deliberation_round_id);
CREATE INDEX IF NOT EXISTS idx_consensus_audit_actor ON consensus_audit_trail(actor_agent);
CREATE INDEX IF NOT EXISTS idx_consensus_audit_occurred ON consensus_audit_trail(occurred_at DESC);

-- Composite index for event lookup
CREATE INDEX IF NOT EXISTS idx_consensus_audit_event_proposal ON consensus_audit_trail(proposal_id, event_type);

-- ============================================================================
-- SECTION 6: Functions
-- ============================================================================

-- Function to update timestamp on row update
CREATE OR REPLACE FUNCTION update_consensus_enhancement_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to start a new deliberation round
CREATE OR REPLACE FUNCTION start_deliberation_round(
    proposal_id_param UUID,
    round_type_param VARCHAR DEFAULT 'voting',
    timeout_seconds INTEGER DEFAULT 120
)
RETURNS UUID AS $$
DECLARE
    new_round_id UUID;
    next_round_number INTEGER;
BEGIN
    -- Get next round number
    SELECT COALESCE(MAX(round_number), 0) + 1 INTO next_round_number
    FROM deliberation_rounds
    WHERE proposal_id = proposal_id_param;

    -- Create new round
    INSERT INTO deliberation_rounds (
        proposal_id,
        round_number,
        round_type,
        state,
        voting_timeout_seconds,
        started_at
    ) VALUES (
        proposal_id_param,
        next_round_number,
        round_type_param,
        'active',
        timeout_seconds,
        NOW()
    ) RETURNING id INTO new_round_id;

    -- Record audit event
    INSERT INTO consensus_audit_trail (
        event_type,
        proposal_id,
        deliberation_round_id,
        event_description,
        event_data
    ) VALUES (
        'round_started',
        proposal_id_param,
        new_round_id,
        format('Deliberation round %s started', next_round_number),
        jsonb_build_object('round_type', round_type_param, 'timeout', timeout_seconds)
    );

    RETURN new_round_id;
END;
$$ LANGUAGE plpgsql;

-- Function to complete a deliberation round
CREATE OR REPLACE FUNCTION complete_deliberation_round(
    round_id_param UUID,
    consensus_reached_param BOOLEAN,
    consensus_score_param FLOAT,
    summary_param TEXT
)
RETURNS void AS $$
BEGIN
    UPDATE deliberation_rounds
    SET
        state = 'completed',
        consensus_reached = consensus_reached_param,
        consensus_score = consensus_score_param,
        round_summary = summary_param,
        completed_at = NOW()
    WHERE id = round_id_param;

    -- Record audit event
    INSERT INTO consensus_audit_trail (
        event_type,
        proposal_id,
        deliberation_round_id,
        event_description,
        event_data
    )
    SELECT
        'round_completed',
        proposal_id,
        round_id_param,
        format('Deliberation round %s completed', round_number),
        jsonb_build_object(
            'consensus_reached', consensus_reached_param,
            'consensus_score', consensus_score_param
        )
    FROM deliberation_rounds
    WHERE id = round_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to record an argument
CREATE OR REPLACE FUNCTION record_deliberation_argument(
    round_id_param UUID,
    proposal_id_param UUID,
    arg_type VARCHAR,
    arg_text TEXT,
    agent_id_param VARCHAR,
    parent_arg_id UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    new_arg_id UUID;
BEGIN
    INSERT INTO deliberation_arguments (
        deliberation_round_id,
        proposal_id,
        argument_type,
        argument_text,
        agent_id,
        parent_argument_id
    ) VALUES (
        round_id_param,
        proposal_id_param,
        arg_type,
        arg_text,
        agent_id_param,
        parent_arg_id
    ) RETURNING id INTO new_arg_id;

    -- Record audit event
    INSERT INTO consensus_audit_trail (
        event_type,
        proposal_id,
        deliberation_round_id,
        argument_id,
        actor_agent,
        event_description,
        event_data
    ) VALUES (
        'argument_submitted',
        proposal_id_param,
        round_id_param,
        new_arg_id,
        agent_id_param,
        format('Argument submitted: %s', arg_type),
        jsonb_build_object('argument_text', left(arg_text, 100))
    );

    RETURN new_arg_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update agent expertise
CREATE OR REPLACE FUNCTION update_agent_expertise(
    agent_id_param VARCHAR,
    agent_name_param VARCHAR,
    domain_param VARCHAR,
    subdomain_param VARCHAR DEFAULT NULL,
    outcome_success BOOLEAN DEFAULT NULL
)
RETURNS void AS $$
DECLARE
    current_score FLOAT;
    current_experience INTEGER;
    current_success INTEGER;
    new_score FLOAT;
BEGIN
    -- Check if profile exists
    SELECT expertise_score, experience_count, success_count
    INTO current_score, current_experience, current_success
    FROM agent_expertise_profiles
    WHERE agent_id = agent_id_param
      AND domain = domain_param
      AND (subdomain = subdomain_param OR (subdomain IS NULL AND subdomain_param IS NULL));

    IF FOUND THEN
        -- Update existing profile
        new_score := CASE
            WHEN outcome_success THEN LEAST(1.0, current_score + 0.02)
            ELSE GREATEST(0.0, current_score - 0.01)
        END;

        UPDATE agent_expertise_profiles
        SET
            expertise_score = new_score,
            experience_count = experience_count + 1,
            success_count = CASE WHEN outcome_success THEN success_count + 1 ELSE success_count END,
            last_active_at = NOW(),
            updated_at = NOW()
        WHERE agent_id = agent_id_param
          AND domain = domain_param
          AND (subdomain = subdomain_param OR (subdomain IS NULL AND subdomain_param IS NULL));
    ELSE
        -- Create new profile
        INSERT INTO agent_expertise_profiles (
            agent_id,
            agent_name,
            domain,
            subdomain,
            expertise_score,
            experience_count,
            success_count,
            last_active_at
        ) VALUES (
            agent_id_param,
            agent_name_param,
            domain_param,
            subdomain_param,
            CASE WHEN outcome_success THEN 0.52 ELSE 0.48 END,
            1,
            CASE WHEN outcome_success THEN 1 ELSE 0 END,
            NOW()
        );
    END IF;

    -- Record audit event
    INSERT INTO consensus_audit_trail (
        event_type,
        actor_agent,
        event_description,
        event_data
    ) VALUES (
        'expertise_updated',
        agent_id_param,
        format('Expertise updated for domain %s', domain_param),
        jsonb_build_object(
            'domain', domain_param,
            'subdomain', subdomain_param,
            'outcome_success', outcome_success
        )
    );
END;
$$ LANGUAGE plpgsql;

-- Function to record any consensus event
CREATE OR REPLACE FUNCTION record_consensus_event(
    event_type_param VARCHAR DEFAULT NULL,
    proposal_id_param UUID DEFAULT NULL,
    round_id_param UUID DEFAULT NULL,
    vote_id_param UUID DEFAULT NULL,
    argument_id_param UUID DEFAULT NULL,
    actor_param VARCHAR DEFAULT NULL,
    description_param TEXT DEFAULT NULL,
    data_param JSONB DEFAULT '{}'
)
RETURNS void AS $$
BEGIN
    INSERT INTO consensus_audit_trail (
        event_type,
        proposal_id,
        deliberation_round_id,
        vote_id,
        argument_id,
        actor_agent,
        event_description,
        event_data
    ) VALUES (
        event_type_param,
        proposal_id_param,
        round_id_param,
        vote_id_param,
        argument_id_param,
        actor_param,
        description_param,
        data_param
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: Triggers
-- ============================================================================

-- Auto-update timestamps for deliberation_rounds
DROP TRIGGER IF EXISTS update_deliberation_rounds_timestamp ON deliberation_rounds;
CREATE TRIGGER update_deliberation_rounds_timestamp
    BEFORE UPDATE ON deliberation_rounds
    FOR EACH ROW
    EXECUTE FUNCTION update_consensus_enhancement_timestamp();

-- Auto-update timestamps for deliberation_arguments
DROP TRIGGER IF EXISTS update_deliberation_arguments_timestamp ON deliberation_arguments;
CREATE TRIGGER update_deliberation_arguments_timestamp
    BEFORE UPDATE ON deliberation_arguments
    FOR EACH ROW
    EXECUTE FUNCTION update_consensus_enhancement_timestamp();

-- Auto-update timestamps for agent_expertise_profiles
DROP TRIGGER IF EXISTS update_agent_expertise_profiles_timestamp ON agent_expertise_profiles;
CREATE TRIGGER update_agent_expertise_profiles_timestamp
    BEFORE UPDATE ON agent_expertise_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_consensus_enhancement_timestamp();

-- ============================================================================
-- SECTION 8: Views
-- ============================================================================

-- View for active deliberation rounds
CREATE OR REPLACE VIEW active_deliberation_rounds AS
SELECT
    dr.*,
    cp.proposal_title,
    cp.proposal_type
FROM deliberation_rounds dr
JOIN consensus_proposals cp ON dr.proposal_id = cp.id
WHERE dr.state = 'active'
ORDER BY dr.started_at DESC;

-- View for agent expertise summary
CREATE OR REPLACE VIEW agent_expertise_summary AS
SELECT
    agent_id,
    agent_name,
    domain,
    subdomain,
    expertise_score,
    confidence_level,
    experience_count,
    success_count,
    CASE WHEN experience_count > 0
         THEN ROUND((success_count::NUMERIC / NULLIF(experience_count, 0)) * 100, 2)::NUMERIC
         ELSE 0
    END AS success_rate,
    voting_weight_modifier,
    last_active_at
FROM agent_expertise_profiles
WHERE expires_at IS NULL OR expires_at > NOW()
ORDER BY domain, expertise_score DESC;

-- View for domain experts (top expertise per domain)
CREATE OR REPLACE VIEW domain_experts AS
SELECT DISTINCT ON (domain, subdomain)
    agent_id,
    agent_name,
    domain,
    subdomain,
    expertise_score,
    experience_count,
    success_count,
    voting_weight_modifier
FROM agent_expertise_profiles
WHERE expertise_score >= 0.7
  AND experience_count >= 3
  AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY domain, subdomain, expertise_score DESC;

-- View for deliberation history per proposal
CREATE OR REPLACE VIEW proposal_deliberation_history AS
SELECT
    cp.id AS proposal_id,
    cp.proposal_title,
    cp.proposal_type,
    cp.state,
    COUNT(dr.id) AS total_rounds,
    MAX(dr.round_number) AS latest_round,
    MAX(CASE WHEN dr.consensus_reached THEN dr.completed_at END) AS consensus_reached_at,
    AVG(dr.consensus_score) AS avg_consensus_score
FROM consensus_proposals cp
LEFT JOIN deliberation_rounds dr ON cp.id = dr.proposal_id
GROUP BY cp.id, cp.proposal_title, cp.proposal_type, cp.state;

-- View for argument quality analysis
CREATE OR REPLACE VIEW argument_quality_analysis AS
SELECT
    da.id,
    da.argument_type,
    da.argument_text,
    da.agent_id,
    da.quality_score,
    da.relevance_score,
    da.upvotes - da.downvotes AS net_votes,
    da.influenced_votes,
    dr.round_number,
    cp.proposal_title
FROM deliberation_arguments da
JOIN deliberation_rounds dr ON da.deliberation_round_id = dr.id
JOIN consensus_proposals cp ON da.proposal_id = cp.id
ORDER BY da.quality_score DESC, da.influenced_votes DESC;

-- View for complete audit trail
CREATE OR REPLACE VIEW consensus_full_audit AS
SELECT
    cat.*,
    cp.proposal_title,
    dr.round_number,
    da.argument_type
FROM consensus_audit_trail cat
LEFT JOIN consensus_proposals cp ON cat.proposal_id = cp.id
LEFT JOIN deliberation_rounds dr ON cat.deliberation_round_id = dr.id
LEFT JOIN deliberation_arguments da ON cat.argument_id = da.id
ORDER BY cat.occurred_at DESC;

-- ============================================================================
-- SECTION 9: Comments
-- ============================================================================

COMMENT ON TABLE deliberation_rounds IS 'Multi-round deliberation tracking for complex consensus decisions';
COMMENT ON TABLE deliberation_arguments IS 'Argument exchange logs during deliberation rounds';
COMMENT ON TABLE agent_expertise_profiles IS 'Dynamic expertise scoring for weighted voting';
COMMENT ON TABLE consensus_audit_trail IS 'Complete audit trail for consensus decisions';

COMMENT ON COLUMN deliberation_rounds.round_type IS 'Type: voting, discussion, refinement, final';
COMMENT ON COLUMN deliberation_rounds.consensus_score IS 'Calculated consensus level (0-1)';

COMMENT ON COLUMN deliberation_arguments.argument_type IS 'Type: proposal, support, oppose, question, clarification, amendment';
COMMENT ON COLUMN deliberation_arguments.influenced_votes IS 'Count of votes changed after this argument';

COMMENT ON COLUMN agent_expertise_profiles.expertise_score IS 'Expertise level in domain (0-1)';
COMMENT ON COLUMN agent_expertise_profiles.voting_weight_modifier IS 'Multiplier for vote weight in this domain';
COMMENT ON COLUMN agent_expertise_profiles.decay_rate IS 'Monthly decay rate for expertise score';

COMMENT ON COLUMN consensus_audit_trail.event_type IS 'Type of audited event';
COMMENT ON COLUMN consensus_audit_trail.signature_hash IS 'Hash for integrity verification';

-- ============================================================================
-- SECTION 10: Migration Registration
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        INSERT INTO schema_migrations (version, applied_at)
        VALUES ('006', NOW())
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- Tables created:
--   - deliberation_rounds (multi-round voting)
--   - deliberation_arguments (argument exchange)
--   - agent_expertise_profiles (dynamic expertise)
--   - consensus_audit_trail (complete audit history)
--
-- Functions created:
--   - update_consensus_enhancement_timestamp()
--   - start_deliberation_round()
--   - complete_deliberation_round()
--   - record_deliberation_argument()
--   - update_agent_expertise()
--   - record_consensus_event()
--
-- Views created:
--   - active_deliberation_rounds
--   - agent_expertise_summary
--   - domain_experts
--   - proposal_deliberation_history
--   - argument_quality_analysis
--   - consensus_full_audit
-- ============================================================================
