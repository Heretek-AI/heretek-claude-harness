-- Migration: Create infrastructure_config table for service discovery
-- Version: 1.0.0
-- Purpose: Stores infrastructure service connection details used by CLI config loader

CREATE TABLE IF NOT EXISTS infrastructure_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(100) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 0,
    connection_url TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    health_status VARCHAR(50) DEFAULT 'unknown',
    last_health_check TIMESTAMP WITH TIME ZONE,
    health_check_latency_ms INTEGER,
    health_check_error TEXT,
    extra_config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(service)
);

CREATE INDEX IF NOT EXISTS idx_infrastructure_config_service ON infrastructure_config(service);
CREATE INDEX IF NOT EXISTS idx_infrastructure_config_enabled ON infrastructure_config(is_enabled);
CREATE INDEX IF NOT EXISTS idx_infrastructure_config_health ON infrastructure_config(health_status) WHERE is_enabled = true;
