-- Migration: Create agent_states table
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Track agent runtime state, health metrics, and consciousness data

-- Create agent_states table
CREATE TABLE IF NOT EXISTS agent_states (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_name VARCHAR(255) NOT NULL UNIQUE,
    agent_type VARCHAR(100) NOT NULL,
    tier VARCHAR(50) NOT NULL,

    -- Runtime state
    state VARCHAR(50) NOT NULL DEFAULT 'initializing',
    health_status VARCHAR(50) NOT NULL DEFAULT 'unknown',
    health_score FLOAT DEFAULT 0.0,

    -- Consciousness metrics
    phi_integration FLOAT DEFAULT 0.0,
    integrated_information FLOAT DEFAULT 0.0,
    free_energy FLOAT DEFAULT 0.0,
    attention_focus FLOAT DEFAULT 0.0,
    global_workspace_activity FLOAT DEFAULT 0.0,

    -- Performance metrics
    messages_processed INTEGER DEFAULT 0,
    messages_per_second FLOAT DEFAULT 0.0,
    avg_response_time_ms FLOAT DEFAULT 0.0,
    error_count INTEGER DEFAULT 0,
    last_error_at TIMESTAMP WITH TIME ZONE,

    -- Resource usage
    memory_usage_mb FLOAT DEFAULT 0.0,
    cpu_usage_percent FLOAT DEFAULT 0.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    last_active TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_agent_states_name ON agent_states(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_states_tier ON agent_states(tier);
CREATE INDEX IF NOT EXISTS idx_agent_states_health ON agent_states(health_status);
CREATE INDEX IF NOT EXISTS idx_agent_states_updated ON agent_states(updated_at DESC);

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_agent_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS update_agent_state_timestamp ON agent_states;
CREATE TRIGGER update_agent_state_timestamp
    BEFORE UPDATE ON agent_states
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_state_timestamp();

-- View for healthy agents
CREATE OR REPLACE VIEW healthy_agents AS
SELECT * FROM agent_states
WHERE health_status = 'healthy'
  AND last_heartbeat > NOW() - INTERVAL '5 minutes'
ORDER BY agent_name;

-- View for agents needing attention
CREATE OR REPLACE VIEW agents_needing_attention AS
SELECT * FROM agent_states
WHERE health_status != 'healthy'
   OR last_heartbeat < NOW() - INTERVAL '5 minutes'
   OR health_score < 0.5
ORDER BY health_score ASC;

-- Comment on table
COMMENT ON TABLE agent_states IS 'Runtime state and health metrics for Heretek Swarm agents';
COMMENT ON COLUMN agent_states.phi_integration IS 'Phi integration metric (IIT consciousness theory)';
COMMENT ON COLUMN agent_states.integrated_information IS 'Integrated information value (IIT)';
COMMENT ON COLUMN agent_states.free_energy IS 'Free energy value (FEP - Free Energy Principle)';
