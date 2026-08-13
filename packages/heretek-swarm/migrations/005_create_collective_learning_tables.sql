-- Migration: Create collective learning tables
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Support collective learning patterns, knowledge transformations, and pattern subscriptions
-- Session: 45 - Database Migrations
--
-- This migration creates tables for:
-- 1. collective_patterns - Store extracted patterns from collective learning (Session 41)
-- 2. knowledge_transformations - Store transformed knowledge between agents
-- 3. pattern_subscriptions - Track agent pattern subscriptions for distributed learning
--
-- All tables are idempotent (CREATE IF NOT EXISTS) and include rollback support

-- ============================================================================
-- SECTION 1: Collective Patterns Table
-- ============================================================================
-- Stores patterns extracted from collective learning across the swarm.
-- Patterns represent shared knowledge, behaviors, or insights discovered by
-- multiple agents through distributed learning processes.

CREATE TABLE IF NOT EXISTS collective_patterns (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identity
    pattern_name VARCHAR(255) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL DEFAULT 'behavioral',
    pattern_category VARCHAR(100),

    -- Pattern content
    pattern_data JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    metadata JSONB DEFAULT '{}',

    -- Pattern confidence and validation
    confidence_score FLOAT DEFAULT 0.5,
    validation_count INTEGER DEFAULT 0,
    validation_threshold FLOAT DEFAULT 0.7,

    -- Pattern origin and lineage
    discovered_by VARCHAR(255) NOT NULL,
    source_agents TEXT[] DEFAULT '{}',
    parent_pattern_id UUID REFERENCES collective_patterns(id) ON DELETE SET NULL,

    -- Pattern lifecycle
    state VARCHAR(50) NOT NULL DEFAULT 'discovered',
    -- States: discovered, validating, validated, deprecated, rejected

    -- Vector embedding for pattern similarity search
    pattern_embedding vector(1536),
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',

    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- SECTION 2: Knowledge Transformations Table
-- ============================================================================
-- Tracks knowledge transformations as they flow between agents.
-- Records how knowledge is adapted, refined, or transformed during
-- collective learning processes.

CREATE TABLE IF NOT EXISTS knowledge_transformations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Transformation identity
    transformation_type VARCHAR(100) NOT NULL,
    -- Types: adaptation, refinement, aggregation, specialization, generalization

    -- Source and target knowledge
    source_knowledge_id UUID,
    source_knowledge_type VARCHAR(100),
    target_knowledge_id UUID,
    target_knowledge_type VARCHAR(100),

    -- Transformation details
    transformation_data JSONB NOT NULL DEFAULT '{}',
    transformation_description TEXT,

    -- Agent involvement
    transforming_agent VARCHAR(255) NOT NULL,
    contributing_agents TEXT[] DEFAULT '{}',

    -- Quality metrics
    quality_score FLOAT DEFAULT 0.5,
    fidelity_score FLOAT DEFAULT 1.0,
    -- fidelity_score: how much original knowledge is preserved

    -- Impact tracking
    impact_score FLOAT DEFAULT 0.0,
    downstream_transformations INTEGER DEFAULT 0,

    -- Validation
    validated BOOLEAN DEFAULT FALSE,
    validated_by TEXT[] DEFAULT '{}',
    validated_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: Pattern Subscriptions Table
-- ============================================================================
-- Tracks which agents are subscribed to which patterns.
-- Enables distributed pattern matching and notification systems.

CREATE TABLE IF NOT EXISTS pattern_subscriptions (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Subscription references
    pattern_id UUID NOT NULL REFERENCES collective_patterns(id) ON DELETE CASCADE,

    -- Subscriber info
    subscriber_agent VARCHAR(255) NOT NULL,
    subscription_type VARCHAR(50) DEFAULT 'active',
    -- Types: active, passive, notification-only

    -- Subscription preferences
    match_threshold FLOAT DEFAULT 0.6,
    notification_frequency VARCHAR(50) DEFAULT 'immediate',
    -- Frequencies: immediate, batch, daily, weekly

    -- Subscription metadata
    subscription_context JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    -- Usage statistics
    matches_received INTEGER DEFAULT 0,
    matches_applied INTEGER DEFAULT 0,
    last_match_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint: one subscription per agent-pattern pair
    UNIQUE(pattern_id, subscriber_agent)
);

-- ============================================================================
-- SECTION 4: Indexes
-- ============================================================================

-- Collective Patterns indexes
CREATE INDEX IF NOT EXISTS idx_collective_patterns_type ON collective_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_category ON collective_patterns(pattern_category);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_state ON collective_patterns(state);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_confidence ON collective_patterns(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_created ON collective_patterns(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_discovered_by ON collective_patterns(discovered_by);
CREATE INDEX IF NOT EXISTS idx_collective_patterns_parent ON collective_patterns(parent_pattern_id);

-- Composite index for pattern lookup by type and state
CREATE INDEX IF NOT EXISTS idx_collective_patterns_type_state ON collective_patterns(pattern_type, state);

-- Knowledge Transformations indexes
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_type ON knowledge_transformations(transformation_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_source ON knowledge_transformations(source_knowledge_id, source_knowledge_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_target ON knowledge_transformations(target_knowledge_id, target_knowledge_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_agent ON knowledge_transformations(transforming_agent);
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_quality ON knowledge_transformations(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_transformations_created ON knowledge_transformations(created_at DESC);

-- Pattern Subscriptions indexes
CREATE INDEX IF NOT EXISTS idx_pattern_subscriptions_pattern ON pattern_subscriptions(pattern_id);
CREATE INDEX IF NOT EXISTS idx_pattern_subscriptions_agent ON pattern_subscriptions(subscriber_agent);
CREATE INDEX IF NOT EXISTS idx_pattern_subscriptions_type ON pattern_subscriptions(subscription_type);
CREATE INDEX IF NOT EXISTS idx_pattern_subscriptions_created ON pattern_subscriptions(created_at DESC);

-- ============================================================================
-- SECTION 5: Functions
-- ============================================================================

-- Function to update timestamp on row update
CREATE OR REPLACE FUNCTION update_collective_learning_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to increment pattern usage count
CREATE OR REPLACE FUNCTION increment_pattern_usage(pattern_id_param UUID)
RETURNS void AS $$
BEGIN
    UPDATE collective_patterns
    SET usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE id = pattern_id_param;
END;
$$ LANGUAGE plpgsql;

-- Function to validate pattern through voting
CREATE OR REPLACE FUNCTION validate_pattern(pattern_id_param UUID, validating_agent VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    current_validations INTEGER;
    current_confidence FLOAT;
BEGIN
    -- Increment validation count
    UPDATE collective_patterns
    SET validation_count = validation_count + 1
    WHERE id = pattern_id_param
    RETURNING validation_count, confidence_score INTO current_validations, current_confidence;

    -- Check if threshold reached
    IF current_validations >= 3 AND current_confidence >= 0.7 THEN
        UPDATE collective_patterns
        SET state = 'validated'
        WHERE id = pattern_id_param;
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to record knowledge transformation chain
CREATE OR REPLACE FUNCTION record_transformation_chain(
    source_id UUID,
    source_type VARCHAR,
    target_id UUID,
    target_type VARCHAR,
    trans_type VARCHAR,
    agent VARCHAR,
    trans_data JSONB
)
RETURNS UUID AS $$
DECLARE
    new_id UUID;
BEGIN
    INSERT INTO knowledge_transformations (
        transformation_type,
        source_knowledge_id,
        source_knowledge_type,
        target_knowledge_id,
        target_knowledge_type,
        transformation_data,
        transforming_agent
    ) VALUES (
        trans_type,
        source_id,
        source_type,
        target_id,
        target_type,
        trans_data,
        agent
    ) RETURNING id INTO new_id;

    -- Increment downstream transformation count on source
    UPDATE knowledge_transformations
    SET downstream_transformations = downstream_transformations + 1
    WHERE target_knowledge_id = source_id AND source_knowledge_type = source_type;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 6: Triggers
-- ============================================================================

-- Auto-update timestamps for collective_patterns
DROP TRIGGER IF EXISTS update_collective_patterns_timestamp ON collective_patterns;
CREATE TRIGGER update_collective_patterns_timestamp
    BEFORE UPDATE ON collective_patterns
    FOR EACH ROW
    EXECUTE FUNCTION update_collective_learning_timestamp();

-- Auto-update timestamps for knowledge_transformations
DROP TRIGGER IF EXISTS update_knowledge_transformations_timestamp ON knowledge_transformations;
CREATE TRIGGER update_knowledge_transformations_timestamp
    BEFORE UPDATE ON knowledge_transformations
    FOR EACH ROW
    EXECUTE FUNCTION update_collective_learning_timestamp();

-- Auto-update timestamps for pattern_subscriptions
DROP TRIGGER IF EXISTS update_pattern_subscriptions_timestamp ON pattern_subscriptions;
CREATE TRIGGER update_pattern_subscriptions_timestamp
    BEFORE UPDATE ON pattern_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_collective_learning_timestamp();

-- ============================================================================
-- SECTION 7: Views
-- ============================================================================

-- View for validated patterns
CREATE OR REPLACE VIEW validated_patterns AS
SELECT * FROM collective_patterns
WHERE state = 'validated'
  AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY confidence_score DESC, validation_count DESC;

-- View for active pattern subscriptions
CREATE OR REPLACE VIEW active_pattern_subscriptions AS
SELECT
    ps.*,
    cp.pattern_name,
    cp.pattern_type
FROM pattern_subscriptions ps
JOIN collective_patterns cp ON ps.pattern_id = cp.id
WHERE ps.subscription_type = 'active'
  AND (ps.expires_at IS NULL OR ps.expires_at > NOW())
  AND cp.state = 'validated';

-- View for knowledge transformation chains
CREATE OR REPLACE VIEW transformation_chains AS
SELECT
    kt.*,
    parent.transformation_type AS parent_type,
    parent.transforming_agent AS parent_agent
FROM knowledge_transformations kt
LEFT JOIN knowledge_transformations parent
    ON kt.source_knowledge_id = parent.target_knowledge_id
    AND kt.source_knowledge_type = parent.target_knowledge_type;

-- View for high-impact transformations
CREATE OR REPLACE VIEW high_impact_transformations AS
SELECT * FROM knowledge_transformations
WHERE impact_score > 0.7
   OR downstream_transformations > 5
ORDER BY impact_score DESC, downstream_transformations DESC;

-- ============================================================================
-- SECTION 8: Comments
-- ============================================================================

COMMENT ON TABLE collective_patterns IS 'Stores patterns extracted from collective learning across the swarm';
COMMENT ON TABLE knowledge_transformations IS 'Tracks knowledge transformations as they flow between agents';
COMMENT ON TABLE pattern_subscriptions IS 'Tracks agent subscriptions to collective patterns';

COMMENT ON COLUMN collective_patterns.pattern_type IS 'Type of pattern: behavioral, structural, procedural, cognitive';
COMMENT ON COLUMN collective_patterns.state IS 'Pattern lifecycle state: discovered, validating, validated, deprecated, rejected';
COMMENT ON COLUMN collective_patterns.confidence_score IS 'Confidence in pattern validity (0-1)';
COMMENT ON COLUMN collective_patterns.pattern_embedding IS 'Vector embedding for semantic pattern matching';

COMMENT ON COLUMN knowledge_transformations.transformation_type IS 'Type: adaptation, refinement, aggregation, specialization, generalization';
COMMENT ON COLUMN knowledge_transformations.fidelity_score IS 'How much original knowledge is preserved (0-1)';
COMMENT ON COLUMN knowledge_transformations.impact_score IS 'Measured impact of this transformation on downstream knowledge';

COMMENT ON COLUMN pattern_subscriptions.subscription_type IS 'Type: active (apply automatically), passive (manual apply), notification-only';
COMMENT ON COLUMN pattern_subscriptions.match_threshold IS 'Minimum pattern match score to trigger notification/application';

-- ============================================================================
-- SECTION 9: Migration Registration
-- ============================================================================

-- Record this migration in the system (if migration tracking table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations') THEN
        INSERT INTO schema_migrations (version, applied_at)
        VALUES ('005', NOW())
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- Tables created:
--   - collective_patterns (pattern storage and validation)
--   - knowledge_transformations (knowledge flow tracking)
--   - pattern_subscriptions (agent pattern subscriptions)
--
-- Functions created:
--   - update_collective_learning_timestamp()
--   - increment_pattern_usage()
--   - validate_pattern()
--   - record_transformation_chain()
--
-- Views created:
--   - validated_patterns
--   - active_pattern_subscriptions
--   - transformation_chains
--   - high_impact_transformations
-- ============================================================================
