-- Migration: Create swarm_memories table
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Long-term memory storage with vector embeddings for Heretek Swarm

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create swarm_memories table
CREATE TABLE IF NOT EXISTS swarm_memories (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Owner context
    agent_id VARCHAR(255) NOT NULL,
    session_id UUID,

    -- Content
    content TEXT NOT NULL,
    content_type VARCHAR(100) DEFAULT 'text/plain',
    metadata JSONB DEFAULT '{}',

    -- Classification
    memory_type VARCHAR(50) NOT NULL DEFAULT 'episodic',
    tier VARCHAR(20) NOT NULL DEFAULT 'persistent',
    tags TEXT[] DEFAULT '{}',

    -- Vector embedding (PGVector)
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    embedding_model VARCHAR(100),
    embedding_dimensions INTEGER,

    -- Lineage
    parent_id UUID,
    source_agent VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,

    -- Scoring
    importance_score FLOAT DEFAULT 0.5,
    decay_rate FLOAT DEFAULT 0.99
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_swarm_memories_agent ON swarm_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_swarm_memories_type ON swarm_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_swarm_memories_created ON swarm_memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_swarm_memories_importance ON swarm_memories(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_swarm_memories_session ON swarm_memories(session_id);

-- Composite index for agent + created_at
CREATE INDEX IF NOT EXISTS idx_swarm_memories_agent_created ON swarm_memories(agent_id, created_at DESC);

-- Composite index for type + created_at
CREATE INDEX IF NOT EXISTS idx_swarm_memories_type_created ON swarm_memories(memory_type, created_at DESC);

-- Vector similarity index (IVFFlat for approximate nearest neighbor)
-- Note: Requires sufficient data before creating (1000+ rows recommended)
-- CREATE INDEX idx_swarm_memories_embedding ON swarm_memories
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Function to update access statistics
CREATE OR REPLACE FUNCTION update_memory_access(memory_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE swarm_memories
    SET access_count = access_count + 1,
        accessed_at = NOW()
    WHERE id = memory_id;
END;
$$ LANGUAGE plpgsql;

-- Function to decay importance scores (run periodically)
CREATE OR REPLACE FUNCTION decay_memory_importance()
RETURNS void AS $$
BEGIN
    UPDATE swarm_memories
    SET importance_score = importance_score * decay_rate
    WHERE created_at < NOW() - INTERVAL '1 hour'
      AND importance_score > 0.1;  -- Don't decay below 0.1
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired memories
CREATE OR REPLACE FUNCTION cleanup_expired_memories()
RETURNS void AS $$
BEGIN
    DELETE FROM swarm_memories
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create a view for active memories (not expired, sufficient importance)
CREATE OR REPLACE VIEW active_memories AS
SELECT * FROM swarm_memories
WHERE (expires_at IS NULL OR expires_at > NOW())
  AND importance_score > 0.1
ORDER BY importance_score DESC;

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON TABLE swarm_memories TO heretek;
-- GRANT EXECUTE ON FUNCTION update_memory_access TO heretek;
-- GRANT EXECUTE ON FUNCTION decay_memory_importance TO heretek;
-- GRANT EXECUTE ON FUNCTION cleanup_expired_memories TO heretek;

-- Test data insertion removed for production use
-- Uncomment below line for testing only:
-- INSERT INTO swarm_memories (agent_id, content, memory_type, importance_score, metadata)
-- VALUES (
--     'system',
--     'Migration 001_create_swarm_memories.sql completed successfully. Heretek Swarm memory system initialized.',
--     'semantic',
--     1.0,
--     '{"migration": "001", "created_by": "system"}'::jsonb
-- );

-- Comment on table
COMMENT ON TABLE swarm_memories IS 'Long-term memory storage for Heretek Swarm agents with vector embeddings';
COMMENT ON COLUMN swarm_memories.embedding IS 'Vector embedding for semantic similarity search (1536 dimensions for OpenAI)';
COMMENT ON COLUMN swarm_memories.importance_score IS 'Importance score (0-1), decays over time based on decay_rate';
COMMENT ON COLUMN swarm_memories.memory_type IS 'Type of memory: episodic, semantic, or working';
