-- Migration: Create external_call_logs table
-- Version: 1.0.0
-- Created: 2026-04-18
-- Purpose: Track external API calls made by agents with encrypted request/response bodies

-- Create external_call_logs table
CREATE TABLE IF NOT EXISTS external_call_logs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identity
    agent_id VARCHAR(255) NOT NULL,
    agent_type VARCHAR(100) NOT NULL,

    -- Call details
    call_type VARCHAR(50) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    duration_ms INTEGER,

    -- Encrypted payload (Fernet encrypted)
    request_headers_encrypted TEXT,
    request_body_encrypted TEXT,
    response_body_encrypted TEXT,

    -- Additional metadata
    tool_name VARCHAR(255),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_external_call_logs_agent_id ON external_call_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_external_call_logs_call_type ON external_call_logs(call_type);
CREATE INDEX IF NOT EXISTS idx_external_call_logs_status_code ON external_call_logs(status_code);
CREATE INDEX IF NOT EXISTS idx_external_call_logs_created_at ON external_call_logs(created_at);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_external_call_logs_agent_created ON external_call_logs(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_external_call_logs_call_type_created ON external_call_logs(call_type, created_at);

-- Comment on table
COMMENT ON TABLE external_call_logs IS 'Tracks external API calls made by agents with encrypted request/response bodies';
COMMENT ON COLUMN external_call_logs.request_headers_encrypted IS 'Fernet-encrypted HTTP headers';
COMMENT ON COLUMN external_call_logs.request_body_encrypted IS 'Fernet-encrypted request body';
COMMENT ON COLUMN external_call_logs.response_body_encrypted IS 'Fernet-encrypted response body';
