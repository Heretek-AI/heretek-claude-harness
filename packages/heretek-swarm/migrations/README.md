# Heretek Swarm - Database Migrations

This directory contains SQL migrations for the Heretek Swarm PostgreSQL database.

## Migrations

### 001_create_swarm_memories.sql
Creates the `swarm_memories` table for long-term memory storage with vector embeddings.

**Features:**
- Vector embeddings using pgvector (1536 dimensions for OpenAI)
- Memory classification (episodic, semantic, working)
- Importance scoring with decay
- Access tracking and statistics
- Automatic cleanup functions

**Tables Created:**
- `swarm_memories` - Main memory storage
- `active_memories` - View for active memories

**Functions Created:**
- `update_memory_access(memory_id)` - Update access statistics
- `decay_memory_importance()` - Decay importance scores over time
- `cleanup_expired_memories()` - Remove expired memories

### 002_create_agent_states.sql
Creates the `agent_states` table for tracking agent runtime state and health.

**Features:**
- Agent health metrics and status
- Consciousness metrics (Phi, IIT, FEP)
- Performance tracking
- Resource usage monitoring

**Tables Created:**
- `agent_states` - Agent runtime state
- `healthy_agents` - View for healthy agents
- `agents_needing_attention` - View for agents requiring intervention

### 003_create_workflow_states.sql
Creates the `workflow_states` table for workflow execution tracking.

**Features:**
- Workflow state and progress tracking
- Checkpointing support
- Lineage tracking (parent/root workflows)
- Error handling and retries

**Tables Created:**
- `workflow_states` - Workflow execution state
- `active_workflows` - View for running workflows
- `workflows_completed_today` - View for recently completed workflows
- `failed_workflows` - View for failed workflows

### 004_create_consensus_votes.sql
Creates tables for multi-agent consensus decision making.

**Features:**
- Proposal creation and management
- Vote tracking with weights
- Quorum and majority requirements
- Automatic vote counting

**Tables Created:**
- `consensus_proposals` - Decision proposals
- `consensus_votes` - Individual agent votes
- `open_proposals` - View for active proposals
- `resolved_proposals` - View for completed proposals

### 005_create_collective_learning_tables.sql (Session 45)
Creates tables for collective learning patterns, knowledge transformations, and pattern subscriptions.

**Features:**
- Pattern extraction and storage from collective learning
- Knowledge transformation tracking between agents
- Pattern subscription system for distributed learning
- Pattern validation through voting
- Vector embeddings for pattern similarity search

**Tables Created:**
- `collective_patterns` - Store extracted patterns from collective learning
- `knowledge_transformations` - Store transformed knowledge between agents
- `pattern_subscriptions` - Track agent pattern subscriptions

**Functions Created:**
- `increment_pattern_usage(pattern_id)` - Increment pattern usage count
- `validate_pattern(pattern_id, agent)` - Validate pattern through voting
- `record_transformation_chain(...)` - Record knowledge transformation chain

**Views Created:**
- `validated_patterns` - View for validated patterns
- `active_pattern_subscriptions` - View for active pattern subscriptions
- `transformation_chains` - View for knowledge transformation chains
- `high_impact_transformations` - View for high-impact transformations

### 006_create_consensus_enhancement_tables.sql (Session 45)
Creates tables for enhanced consensus mechanisms with multi-round deliberation.

**Features:**
- Multi-round deliberation tracking
- Argument exchange logging
- Dynamic expertise scoring for weighted voting
- Complete audit trail for compliance

**Tables Created:**
- `deliberation_rounds` - Multi-round voting records
- `deliberation_arguments` - Argument exchange logs
- `agent_expertise_profiles` - Dynamic expertise scoring
- `consensus_audit_trail` - Complete decision history

**Functions Created:**
- `start_deliberation_round(proposal_id, type, timeout)` - Start new deliberation round
- `complete_deliberation_round(round_id, consensus, score, summary)` - Complete round
- `record_deliberation_argument(...)` - Record argument in deliberation
- `update_agent_expertise(...)` - Update agent expertise based on outcomes
- `record_consensus_event(...)` - Record any consensus event for audit

**Views Created:**
- `active_deliberation_rounds` - View for active deliberation rounds
- `agent_expertise_summary` - View for agent expertise summary
- `domain_experts` - View for top experts per domain
- `proposal_deliberation_history` - View for deliberation history per proposal
- `argument_quality_analysis` - View for argument quality analysis
- `consensus_full_audit` - View for complete audit trail

### 007_create_memory_optimization_tables.sql (Session 45)
Creates tables for memory optimization features including access pattern tracking and tiering.

**Features:**
- Memory access pattern tracking
- Dynamic tier classification (hot/warm/cold/archive)
- Compression metadata and statistics
- Prefetch cache state management

**Tables Created:**
- `memory_access_logs` - Access pattern tracking
- `memory_tier_state` - Current tier classification
- `compression_metadata` - Compression tracking
- `prefetch_cache` - Pre-fetch cache state

**Functions Created:**
- `log_memory_access(...)` - Log memory access
- `update_memory_tier(memory_id, type, new_tier)` - Update memory tier
- `record_compression(...)` - Record compression operation
- `record_prefetch(...)` - Record prefetch cache entry
- `record_cache_hit(cache_id)` / `record_cache_miss(cache_id)` - Track cache performance
- `get_recent_access_count(memory_id, type, hours)` - Get access count

**Views Created:**
- `memory_tier_distribution` - View for tier distribution
- `hot_memory_candidates` / `cold_memory_candidates` - Tier migration candidates
- `compression_effectiveness` - View for compression statistics
- `prefetch_cache_performance` - View for prefetch performance
- `low_performing_prefetch` - View for low-performing prefetch entries
- `recent_access_patterns` - View for recent access patterns
- `memory_requiring_tier_review` - View for memories needing tier review

### 008_create_agent_wiring_state_tables.sql (Session 45)
Creates tables for agent wiring state tracking including learning, memory, and consensus configuration.

**Features:**
- Per-agent learning status and capabilities
- Per-agent memory configuration
- Per-agent consensus participation settings
- Agent wiring state queries

**Tables Created:**
- `agent_learning_state` - Per-agent learning status
- `agent_memory_config` - Per-agent memory configuration
- `agent_consensus_config` - Per-agent consensus participation

**Functions Created:**
- `initialize_agent_learning(agent_id, name, type, enabled)` - Initialize agent learning
- `record_learning_progress(...)` - Record learning progress
- `configure_agent_memory(...)` - Configure agent memory
- `configure_agent_consensus(...)` - Configure consensus participation
- `record_consensus_participation(agent_id, type, success)` - Record participation
- `get_agent_wiring_state(agent_id)` - Get full agent wiring state

**Views Created:**
- `active_learning_agents` - View for active learning agents
- `agent_learning_summary` - View for learning summary by type
- `custom_memory_agents` - View for agents with custom memory config
- `active_consensus_participants` - View for active consensus participants
- `consensus_participation_stats` - View for participation statistics
- `agents_needing_attention` - View for agents requiring intervention

## Qdrant Collections

The `scripts/setup_qdrant_collections.py` script creates vector collections:

### Original Collections (Sessions 1-44)

| Collection | Vector Size | Purpose |
|------------|-------------|---------|
| heretek_rag | 1536 | RAG document embeddings |
| heretek_memory | 1536 | Agent memory embeddings |
| heretek_semantic | 1536 | Semantic knowledge |
| heretek_context | 1536 | Context embeddings |

### Session 45 Additions

| Collection | Vector Size | Purpose |
|------------|-------------|---------|
| heretek_patterns | 1536 | Collective learning pattern vectors |
| heretek_consensus | 1536 | Consensus deliberation embeddings |
| heretek_memory_access | 1536 | Memory access pattern vectors |

**Payload Indexes Created for Session 45:**
- Pattern indexes: pattern_type, pattern_category, state, discovered_by, confidence_score
- Consensus indexes: proposal_type, state, agent_id, round_number
- Memory access indexes: agent_id, access_type, tier, cache_hit

## Running Migrations

### Prerequisites

1. PostgreSQL 15+ with pgvector extension
2. psycopg2-binary Python package
3. Database connection configured via `DATABASE_URL` environment variable

### Execute Migrations

```bash
# Run all pending migrations
python scripts/run_migrations.py

# Check migration status
python scripts/run_migrations.py --status

# Dry run (show what would be executed)
python scripts/run_migrations.py --dry-run
```

### Setup Qdrant Collections

```bash
# Requires qdrant-client package
pip install qdrant-client

# Set Qdrant URL (optional, defaults to http://localhost:6333)
export QDRANT_URL=http://localhost:6333

# Run collection setup
python migrations/scripts/setup_qdrant_collections.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://heretek:heretek@localhost:5432/heretek` |
| `QDRANT_URL` | Qdrant vector store URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API key (optional) | - |

## Database Schema

### swarm_memories

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| agent_id | VARCHAR(255) | Owner agent |
| session_id | UUID | Session context |
| content | TEXT | Memory content |
| content_type | VARCHAR(100) | Content MIME type |
| metadata | JSONB | Additional metadata |
| memory_type | VARCHAR(50) | episodic/semantic/working |
| tier | VARCHAR(20) | persistent/ephemeral |
| tags | TEXT[] | Classification tags |
| embedding | vector(1536) | Vector embedding |
| parent_id | UUID | Parent memory reference |
| importance_score | FLOAT | Importance (0-1) |
| decay_rate | FLOAT | Decay multiplier |

### agent_states

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| agent_name | VARCHAR(255) | Agent identifier |
| state | VARCHAR(50) | Runtime state |
| health_status | VARCHAR(50) | healthy/warning/critical |
| health_score | FLOAT | 0.0-1.0 health metric |
| phi_integration | FLOAT | IIT consciousness metric |
| integrated_information | FLOAT | IIT phi value |
| free_energy | FLOAT | FEP energy value |
| messages_processed | INTEGER | Total messages |
| avg_response_time_ms | FLOAT | Average latency |

### workflow_states

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| workflow_name | VARCHAR(255) | Workflow identifier |
| state | VARCHAR(50) | pending/running/completed/failed |
| progress_percent | FLOAT | 0-100 progress |
| input_data | JSONB | Workflow inputs |
| output_data | JSONB | Workflow outputs |
| parent_workflow_id | UUID | Parent workflow |
| trace_id | UUID | Distributed trace ID |
| last_checkpoint | JSONB | Last checkpoint data |

### consensus_proposals

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| proposal_type | VARCHAR(100) | Proposal category |
| state | VARCHAR(50) | open/passed/rejected |
| votes_for | INTEGER | For vote count |
| votes_against | INTEGER | Against vote count |
| votes_abstain | INTEGER | Abstain vote count |
| required_quorum | FLOAT | Minimum participation |
| required_majority | FLOAT | Required majority |

## Troubleshooting

### pgvector Extension

If pgvector is not available:

```sql
-- Install pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Connection Issues

```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check PostgreSQL is running
pg_isready -h localhost -p 5432
```

### Migration Errors

If a migration fails:

1. Check the error message for details
2. Verify database connection and permissions
3. Ensure pgvector extension is installed
4. Check if table already exists (may need rollback)

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2026-04-07 | Initial migrations (001-004) |
| 1.1.0 | 2026-04-07 | Session 45: Database Migrations (005-008) |

## Session 45 Summary

Session 45 adds comprehensive database migrations for:

1. **Collective Learning** (Migration 005)
   - Pattern storage and validation
   - Knowledge transformation tracking
   - Pattern subscriptions

2. **Consensus Enhancements** (Migration 006)
   - Multi-round deliberation
   - Argument exchange logging
   - Dynamic expertise scoring
   - Complete audit trail

3. **Memory Optimization** (Migration 007)
   - Access pattern tracking
   - Dynamic tier classification
   - Compression metadata
   - Prefetch cache state

4. **Agent Wiring State** (Migration 008)
   - Per-agent learning status
   - Per-agent memory configuration
   - Per-agent consensus participation

**Qdrant Collections Added:**
- heretek_patterns (pattern vectors)
- heretek_consensus (consensus embeddings)
- heretek_memory_access (access pattern vectors)

**Rollback Scripts:**
All migrations include idempotent rollback scripts in `migrations/rollbacks/`
