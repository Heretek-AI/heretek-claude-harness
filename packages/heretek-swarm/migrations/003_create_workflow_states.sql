-- Migration: Create workflow_states table
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Track workflow execution state, progress, and lineage

-- Create workflow_states table
CREATE TABLE IF NOT EXISTS workflow_states (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Workflow identity
    workflow_name VARCHAR(255) NOT NULL,
    workflow_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    workflow_type VARCHAR(100) NOT NULL,

    -- Execution state
    state VARCHAR(50) NOT NULL DEFAULT 'pending',
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    progress_percent FLOAT DEFAULT 0.0,

    -- Context
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',

    -- Lineage
    parent_workflow_id UUID,
    root_workflow_id UUID,
    trace_id UUID,
    span_id UUID,

    -- Agent participation
    participating_agents TEXT[] DEFAULT '{}',
    current_agent VARCHAR(255),

    -- Checkpointing
    last_checkpoint JSONB DEFAULT '{}',
    last_checkpoint_at TIMESTAMP WITH TIME ZONE,
    checkpoint_count INTEGER DEFAULT 0,

    -- Performance
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,

    -- Error handling
    error_message TEXT,
    error_stack TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_workflow_states_name ON workflow_states(workflow_name);
CREATE INDEX IF NOT EXISTS idx_workflow_states_state ON workflow_states(state);
CREATE INDEX IF NOT EXISTS idx_workflow_states_status ON workflow_states(status);
CREATE INDEX IF NOT EXISTS idx_workflow_states_created ON workflow_states(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_states_trace ON workflow_states(trace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_states_parent ON workflow_states(parent_workflow_id);

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_workflow_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    IF NEW.state = 'completed' AND NEW.completed_at IS NULL THEN
        NEW.completed_at = NOW();
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS update_workflow_state_timestamp ON workflow_states;
CREATE TRIGGER update_workflow_state_timestamp
    BEFORE UPDATE ON workflow_states
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_state_timestamp();

-- View for active workflows
CREATE OR REPLACE VIEW active_workflows AS
SELECT * FROM workflow_states
WHERE state IN ('running', 'pending', 'waiting')
ORDER BY created_at DESC;

-- View for completed workflows today
CREATE OR REPLACE VIEW workflows_completed_today AS
SELECT * FROM workflow_states
WHERE state = 'completed'
  AND completed_at >= NOW() - INTERVAL '24 hours'
ORDER BY completed_at DESC;

-- View for failed workflows
CREATE OR REPLACE VIEW failed_workflows AS
SELECT * FROM workflow_states
WHERE state = 'failed'
   OR status = 'error'
ORDER BY updated_at DESC;

-- Comment on table
COMMENT ON TABLE workflow_states IS 'Workflow execution state and progress tracking for Heretek Swarm';
