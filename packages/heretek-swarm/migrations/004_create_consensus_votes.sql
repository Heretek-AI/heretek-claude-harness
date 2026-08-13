-- Migration: Create consensus_votes table
-- Version: 1.0.0
-- Created: 2026-04-07
-- Purpose: Track consensus proposals and votes for multi-agent decision making

-- Create consensus_proposals table
CREATE TABLE IF NOT EXISTS consensus_proposals (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Proposal identity
    proposal_type VARCHAR(100) NOT NULL,
    proposal_title VARCHAR(500) NOT NULL,
    proposal_description TEXT,

    -- Content
    proposal_data JSONB NOT NULL DEFAULT '{}',
    context JSONB DEFAULT '{}',

    -- State
    state VARCHAR(50) NOT NULL DEFAULT 'open',
    result VARCHAR(50),

    -- Voting parameters
    voting_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    voting_end TIMESTAMP WITH TIME ZONE,
    voting_timeout_seconds INTEGER DEFAULT 300,
    required_quorum FLOAT DEFAULT 0.5,
    required_majority FLOAT DEFAULT 0.67,

    -- Vote counts
    votes_for INTEGER DEFAULT 0,
    votes_against INTEGER DEFAULT 0,
    votes_abstain INTEGER DEFAULT 0,
    total_votes INTEGER DEFAULT 0,

    -- Origin
    proposed_by VARCHAR(255) NOT NULL,
    proposer_agent VARCHAR(255) NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Create consensus_votes table
CREATE TABLE IF NOT EXISTS consensus_votes (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key
    proposal_id UUID NOT NULL REFERENCES consensus_proposals(id) ON DELETE CASCADE,

    -- Vote details
    voter_agent VARCHAR(255) NOT NULL,
    vote VARCHAR(20) NOT NULL CHECK (vote IN ('for', 'against', 'abstain')),
    vote_weight FLOAT DEFAULT 1.0,

    -- Reasoning
    reasoning TEXT,
    vote_data JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(proposal_id, voter_agent)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_consensus_proposals_state ON consensus_proposals(state);
CREATE INDEX IF NOT EXISTS idx_consensus_proposals_type ON consensus_proposals(proposal_type);
CREATE INDEX IF NOT EXISTS idx_consensus_proposals_created ON consensus_proposals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consensus_votes_proposal ON consensus_votes(proposal_id);
CREATE INDEX IF NOT EXISTS idx_consensus_votes_voter ON consensus_votes(voter_agent);

-- Function to update proposal timestamp
CREATE OR REPLACE FUNCTION update_proposal_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS update_proposal_timestamp ON consensus_proposals;
CREATE TRIGGER update_proposal_timestamp
    BEFORE UPDATE ON consensus_proposals
    FOR EACH ROW
    EXECUTE FUNCTION update_proposal_timestamp();

-- Function to update vote counts
CREATE OR REPLACE FUNCTION update_proposal_vote_counts()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE consensus_proposals
    SET
        votes_for = (SELECT COUNT(*) FROM consensus_votes WHERE proposal_id = NEW.proposal_id AND vote = 'for'),
        votes_against = (SELECT COUNT(*) FROM consensus_votes WHERE proposal_id = NEW.proposal_id AND vote = 'against'),
        votes_abstain = (SELECT COUNT(*) FROM consensus_votes WHERE proposal_id = NEW.proposal_id AND vote = 'abstain'),
        total_votes = (SELECT COUNT(*) FROM consensus_votes WHERE proposal_id = NEW.proposal_id),
        updated_at = NOW()
    WHERE id = NEW.proposal_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update vote counts
DROP TRIGGER IF EXISTS update_proposal_vote_counts ON consensus_votes;
CREATE TRIGGER update_proposal_vote_counts
    AFTER INSERT OR UPDATE ON consensus_votes
    FOR EACH ROW
    EXECUTE FUNCTION update_proposal_vote_counts();

-- View for open proposals
CREATE OR REPLACE VIEW open_proposals AS
SELECT * FROM consensus_proposals
WHERE state = 'open'
  AND (voting_end IS NULL OR voting_end > NOW())
ORDER BY created_at DESC;

-- View for resolved proposals
CREATE OR REPLACE VIEW resolved_proposals AS
SELECT * FROM consensus_proposals
WHERE state IN ('passed', 'rejected', 'expired')
ORDER BY resolved_at DESC;

-- Comment on tables
COMMENT ON TABLE consensus_proposals IS 'Consensus proposals for multi-agent decision making';
COMMENT ON TABLE consensus_votes IS 'Votes on consensus proposals from individual agents';
