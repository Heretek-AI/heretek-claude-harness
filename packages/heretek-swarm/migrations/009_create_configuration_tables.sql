-- Migration: Create configuration tables for dynamic configuration management
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Database-backed configuration for Heretek Swarm with multi-provider LLM support

-- =============================================================================
-- User Configurations Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_configurations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Configuration key (unique identifier)
    config_key VARCHAR(255) NOT NULL UNIQUE,

    -- Configuration value (JSON for flexible storage)
    config_value JSONB NOT NULL DEFAULT '{}',

    -- Configuration type for validation
    config_type VARCHAR(50) NOT NULL DEFAULT 'string',

    -- Description and documentation
    description TEXT,
    category VARCHAR(100) DEFAULT 'general',

    -- Metadata
    is_sensitive BOOLEAN DEFAULT FALSE,
    is_editable BOOLEAN DEFAULT TRUE,
    validation_schema JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_user_configurations_key ON user_configurations(config_key);
CREATE INDEX IF NOT EXISTS idx_user_configurations_category ON user_configurations(category);

-- =============================================================================
-- LLM Providers Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_providers (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provider identification
    provider_name VARCHAR(100) NOT NULL UNIQUE,
    provider_type VARCHAR(50) NOT NULL,

    -- Connection configuration
    base_url VARCHAR(500) NOT NULL,
    api_key_encrypted TEXT,
    api_key_hint VARCHAR(100),

    -- Model configuration
    default_model VARCHAR(255),
    available_models JSONB DEFAULT '[]',
    model_aliases JSONB DEFAULT '{}',

    -- Provider capabilities
    supports_streaming BOOLEAN DEFAULT TRUE,
    supports_function_calling BOOLEAN DEFAULT FALSE,
    supports_vision BOOLEAN DEFAULT FALSE,
    max_tokens INTEGER,
    max_context_length INTEGER,

    -- Rate limiting
    rate_limit_requests_per_minute INTEGER,
    rate_limit_tokens_per_minute INTEGER,

    -- Status and health
    is_enabled BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    health_status VARCHAR(50) DEFAULT 'unknown',
    last_health_check TIMESTAMP WITH TIME ZONE,
    health_check_error TEXT,

    -- Priority for fallback chain
    priority INTEGER DEFAULT 100,

    -- Additional configuration
    extra_config JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_provider_type CHECK (
        provider_type IN (
            'openai',
            'openai_compatible',
            'ollama',
            'llamacpp',
            'zai',
            'minimax',
            'lemonade'
        )
    ),
    CONSTRAINT valid_health_status CHECK (
        health_status IN ('healthy', 'unhealthy', 'unknown', 'degraded')
    )
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_llm_providers_type ON llm_providers(provider_type);
CREATE INDEX IF NOT EXISTS idx_llm_providers_enabled ON llm_providers(is_enabled);
CREATE INDEX IF NOT EXISTS idx_llm_providers_default ON llm_providers(is_default);
CREATE INDEX IF NOT EXISTS idx_llm_providers_priority ON llm_providers(priority);

-- =============================================================================
-- Embedding Providers Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS embedding_providers (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provider identification
    provider_name VARCHAR(100) NOT NULL UNIQUE,
    provider_type VARCHAR(50) NOT NULL,

    -- Connection configuration
    base_url VARCHAR(500) NOT NULL,
    api_key_encrypted TEXT,
    api_key_hint VARCHAR(100),

    -- Model configuration
    default_model VARCHAR(255),
    available_models JSONB DEFAULT '[]',

    -- Embedding configuration
    embedding_dimensions INTEGER,
    supported_input_formats JSONB DEFAULT '["text"]',
    max_batch_size INTEGER DEFAULT 32,
    max_tokens_per_batch INTEGER DEFAULT 8192,

    -- Status and health
    is_enabled BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    health_status VARCHAR(50) DEFAULT 'unknown',
    last_health_check TIMESTAMP WITH TIME ZONE,
    health_check_error TEXT,

    -- Priority for fallback chain
    priority INTEGER DEFAULT 100,

    -- Additional configuration
    extra_config JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_embedding_provider_type CHECK (
        provider_type IN (
            'openai',
            'openai_compatible',
            'ollama',
            'local',
            'huggingface'
        )
    ),
    CONSTRAINT valid_health_status CHECK (
        health_status IN ('healthy', 'unhealthy', 'unknown', 'degraded')
    )
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_embedding_providers_type ON embedding_providers(provider_type);
CREATE INDEX IF NOT EXISTS idx_embedding_providers_enabled ON embedding_providers(is_enabled);
CREATE INDEX IF NOT EXISTS idx_embedding_providers_default ON embedding_providers(is_default);

-- =============================================================================
-- Agent Configurations Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_configs (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identification
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(255),

    -- Configuration
    config_name VARCHAR(255) NOT NULL,
    config_data JSONB NOT NULL DEFAULT '{}',

    -- LLM binding
    llm_provider_id UUID REFERENCES llm_providers(id),
    embedding_provider_id UUID REFERENCES embedding_providers(id),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_default_for_type BOOLEAN DEFAULT FALSE,

    -- Metadata
    description TEXT,
    tags TEXT[] DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_agent_configs_type ON agent_configs(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_configs_agent_id ON agent_configs(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_configs_active ON agent_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_agent_configs_default ON agent_configs(is_default_for_type);

-- =============================================================================
-- Configuration Audit Log
-- =============================================================================

CREATE TABLE IF NOT EXISTS config_audit_log (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Audit information
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,

    -- Change details
    old_value JSONB,
    new_value JSONB,
    changed_fields TEXT[],

    -- Actor information
    changed_by VARCHAR(255),
    change_reason TEXT,
    ip_address INET,

    -- Timestamp
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_config_audit_entity ON config_audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_config_audit_action ON config_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_config_audit_changed_at ON config_audit_log(changed_at DESC);

-- =============================================================================
-- Configuration Cache Table (for frequently accessed configs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS config_cache (
    -- Primary key
    cache_key VARCHAR(255) PRIMARY KEY,

    -- Cached value
    cache_value JSONB NOT NULL,

    -- Expiration
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for cleanup
CREATE INDEX IF NOT EXISTS idx_config_cache_expires ON config_cache(expires_at);

-- =============================================================================
-- Functions
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update cache access
CREATE OR REPLACE FUNCTION update_cache_access()
RETURNS TRIGGER AS $$
BEGIN
    NEW.access_count = OLD.access_count + 1;
    NEW.last_accessed_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM config_cache
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to log configuration changes
CREATE OR REPLACE FUNCTION log_config_change(
    p_entity_type VARCHAR,
    p_entity_id UUID,
    p_action VARCHAR,
    p_old_value JSONB,
    p_new_value JSONB,
    p_changed_by VARCHAR,
    p_change_reason TEXT
)
RETURNS void AS $$
BEGIN
    INSERT INTO config_audit_log (
        entity_type,
        entity_id,
        action,
        old_value,
        new_value,
        changed_by,
        change_reason
    ) VALUES (
        p_entity_type,
        p_entity_id,
        p_action,
        p_old_value,
        p_new_value,
        p_changed_by,
        p_change_reason
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Triggers
-- =============================================================================

-- Trigger to update updated_at on user_configurations
CREATE TRIGGER trg_update_user_configurations
    BEFORE UPDATE ON user_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_config_updated_at();

-- Trigger to update updated_at on llm_providers
CREATE TRIGGER trg_update_llm_providers
    BEFORE UPDATE ON llm_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_config_updated_at();

-- Trigger to update updated_at on embedding_providers
CREATE TRIGGER trg_update_embedding_providers
    BEFORE UPDATE ON embedding_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_config_updated_at();

-- Trigger to update updated_at on agent_configs
CREATE TRIGGER trg_update_agent_configs
    BEFORE UPDATE ON agent_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_config_updated_at();

-- Trigger to update cache access
CREATE TRIGGER trg_update_cache_access
    BEFORE UPDATE ON config_cache
    FOR EACH ROW
    WHEN (OLD.cache_value IS NOT DISTINCT FROM NEW.cache_value)
    EXECUTE FUNCTION update_cache_access();

-- =============================================================================
-- Views
-- =============================================================================

-- View for active LLM providers
CREATE OR REPLACE VIEW active_llm_providers AS
SELECT * FROM llm_providers
WHERE is_enabled = TRUE
ORDER BY priority ASC, provider_name ASC;

-- View for active embedding providers
CREATE OR REPLACE VIEW active_embedding_providers AS
SELECT * FROM embedding_providers
WHERE is_enabled = TRUE
ORDER BY priority ASC, provider_name ASC;

-- View for default agent configurations
CREATE OR REPLACE VIEW default_agent_configs AS
SELECT * FROM agent_configs
WHERE is_default_for_type = TRUE AND is_active = TRUE;

-- View for recent configuration changes
CREATE OR REPLACE VIEW recent_config_changes AS
SELECT * FROM config_audit_log
WHERE changed_at > NOW() - INTERVAL '7 days'
ORDER BY changed_at DESC;

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Insert default system configurations
INSERT INTO user_configurations (config_key, config_value, config_type, description, category) VALUES
    ('system.name', '"Heretek Swarm"', 'string', 'System display name', 'system'),
    ('system.version', '"0.2.0"', 'string', 'Current system version', 'system'),
    ('system.environment', '"development"', 'string', 'Deployment environment', 'system'),
    ('rate_limit.enabled', 'true', 'boolean', 'Enable rate limiting', 'rate_limiting'),
    ('rate_limit.default_rpm', '60', 'integer', 'Default requests per minute limit', 'rate_limiting'),
    ('rate_limit.default_tpm', '100000', 'integer', 'Default tokens per minute limit', 'rate_limiting'),
    ('memory.default_ttl', '3600', 'integer', 'Default memory TTL in seconds', 'memory'),
    ('memory.max_size', '10000', 'integer', 'Maximum memory entries per agent', 'memory'),
    ('consciousness.phi_threshold', '0.6', 'float', 'Default phi consciousness threshold', 'consciousness'),
    ('consensus.min_votes', '3', 'integer', 'Minimum votes for consensus', 'consensus'),
    ('consensus.confidence_threshold', '0.6', 'float', 'Confidence threshold for consensus', 'consensus')
ON CONFLICT (config_key) DO NOTHING;

-- Insert default LLM provider (OpenAI placeholder)
INSERT INTO llm_providers (
    provider_name,
    provider_type,
    base_url,
    api_key_hint,
    default_model,
    is_enabled,
    is_default,
    priority,
    supports_streaming,
    supports_function_calling,
    extra_config
) VALUES (
    'openai-default',
    'openai',
    'https://api.openai.com/v1',
    'sk-...',
    'gpt-4o',
    FALSE,
    TRUE,
    1,
    TRUE,
    TRUE,
    '{"temperature_range": {"min": 0, "max": 2}, "top_p_range": {"min": 0, "max": 1}}'::jsonb
)
ON CONFLICT (provider_name) DO NOTHING;

-- Insert default embedding provider (OpenAI placeholder)
INSERT INTO embedding_providers (
    provider_name,
    provider_type,
    base_url,
    api_key_hint,
    default_model,
    embedding_dimensions,
    is_enabled,
    is_default,
    priority
) VALUES (
    'openai-embeddings',
    'openai',
    'https://api.openai.com/v1',
    'sk-...',
    'text-embedding-3-small',
    1536,
    FALSE,
    TRUE,
    1
)
ON CONFLICT (provider_name) DO NOTHING;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE user_configurations IS 'User-defined system configurations with validation';
COMMENT ON TABLE llm_providers IS 'LLM provider configurations for multi-provider support';
COMMENT ON TABLE embedding_providers IS 'Embedding provider configurations for vector operations';
COMMENT ON TABLE agent_configs IS 'Per-agent configuration overrides and defaults';
COMMENT ON TABLE config_audit_log IS 'Audit trail for all configuration changes';
COMMENT ON TABLE config_cache IS 'Cache for frequently accessed configuration values';

COMMENT ON COLUMN llm_providers.provider_type IS 'Provider type: openai, openai_compatible, ollama, llamacpp, zai, minimax, lemonade';
COMMENT ON COLUMN embedding_providers.provider_type IS 'Provider type: openai, openai_compatible, ollama, local, huggingface';
COMMENT ON COLUMN llm_providers.api_key_encrypted IS 'Encrypted API key (use application-level encryption)';
COMMENT ON COLUMN embedding_providers.api_key_encrypted IS 'Encrypted API key (use application-level encryption)';

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO heretek;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO heretek;
