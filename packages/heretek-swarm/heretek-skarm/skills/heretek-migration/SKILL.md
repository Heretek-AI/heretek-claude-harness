---
name: heretek-migration
description: >-
  Migration patterns for Heretek Swarm. Use when creating database migrations,
  migrating code between systems, or planning large-scale refactoring. Covers
  Alembic migrations, code migration strategies, and rollback procedures.
---

# Heretek Swarm Migration

## Migration Types

### Database Migrations
- Schema changes (add/remove columns, tables)
- Data migrations (transform existing data)
- Index changes (add/remove indexes)

### Code Migrations
- API changes (breaking/non-breaking)
- Library upgrades (dependency changes)
- Architecture changes (component restructuring)

### Infrastructure Migrations
- Database server changes
- Message broker changes
- Storage system changes

## Database Migrations

### Alembic Setup
```bash
# Initialize Alembic
cd backend
alembic init migrations

# Configure alembic.ini
# Set sqlalchemy.url = postgresql://postgres:password@localhost:5432/heretek_swarm
```

### Creating Migrations
```bash
# Auto-generate migration
alembic revision --autogenerate -m "add_agent_table"

# Create empty migration
alembic revision -m "add_index"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123
```

### Migration File Structure
```python
# migrations/versions/abc123_add_agent_table.py
"""Add agent table

Revision ID: abc123
Revises: def456
Create Date: 2024-01-15 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create agent table
    op.create_table(
        'agents',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now())
    )

    # Add index
    op.create_index(
        'ix_agents_status',
        'agents',
        ['status']
    )

def downgrade():
    # Drop index
    op.drop_index('ix_agents_status')

    # Drop table
    op.drop_table('agents')
```

### Data Migrations
```python
# Migrate existing data
def upgrade():
    # Add new column with default
    op.add_column(
        'agents',
        sa.Column('new_field', sa.String(100), default='default_value')
    )

    # Migrate data
    op.execute("""
        UPDATE agents
        SET new_field = old_field
        WHERE old_field IS NOT NULL
    """)

    # Remove old column
    op.drop_column('agents', 'old_field')
```

### Migration Best Practices
1. **Always backup** before running migrations
2. **Test migrations** on staging first
3. **Write reversible migrations** (upgrade and downgrade)
4. **Handle data carefully** - test data migrations
5. **Use transactions** for atomic changes
6. **Document breaking changes**

## Code Migration Strategies

### API Migration
```python
# Old API
@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    return await get_agent_by_id(agent_id)

# New API (backward compatible)
@router.get("/agents/{agent_id}")
@router.get("/v2/agents/{agent_id}")
async def get_agent(agent_id: str, version: str = "v1"):
    if version == "v2":
        return await get_agent_v2(agent_id)
    return await get_agent_v1(agent_id)
```

### Library Migration
```python
# Step 1: Add new library alongside old
# Step 2: Gradually migrate functionality
# Step 3: Remove old library

# Example: Migrating from legacy memory to Cognee
# Step 1: Add CogneeMemoryReader
# Step 2: Update imports one by one
# Step 3: Remove legacy classes
```

### Architecture Migration
```python
# Monolith to microservices
# Step 1: Extract service interface
class MemoryService(ABC):
    @abstractmethod
    async def search(self, query: str) -> List[Memory]:
        pass

# Step 2: Implement service
class CogneeMemoryService(MemoryService):
    async def search(self, query: str) -> List[Memory]:
        # Cognee implementation
        pass

# Step 3: Update consumers
# Step 4: Remove old implementation
```

## Rollback Procedures

### Database Rollback
```bash
# Rollback migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123

# Check current version
alembic current

# View migration history
alembic history
```

### Code Rollback
```bash
# Git rollback
git revert <commit-hash>

# Or reset to specific commit
git reset --hard <commit-hash>

# Force push (use with caution)
git push --force-with-lease
```

### Infrastructure Rollback
```bash
# Docker rollback
docker compose down
docker compose up -d --build

# Database restore
docker compose exec -T postgres psql -U postgres heretek_swarm < backup.sql
```

## Migration Testing

### Unit Tests
```python
import pytest
from alembic.config import Config
from alembic import command

def test_migration_upgrade():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    # Verify schema changes

def test_migration_downgrade():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "-1")
    # Verify rollback
```

### Integration Tests
```python
@pytest.mark.integration
async def test_migration_with_data():
    # Create test data
    await create_test_agents()

    # Run migration
    run_migration("abc123")

    # Verify data preserved
    agents = await get_all_agents()
    assert len(agents) == 10

    # Verify new schema
    assert hasattr(agents[0], 'new_field')
```

## Migration Planning

### Checklist
1. **Backup data** before migration
2. **Test on staging** environment
3. **Schedule maintenance window** if needed
4. **Notify stakeholders** of changes
5. **Monitor migration progress**
6. **Verify after migration**
7. **Document changes**

### Communication Template
```markdown
## Migration Notice

**Date:** 2024-01-15 10:00 UTC
**Duration:** 30 minutes
**Impact:** API will be unavailable during migration

### Changes
- Added new field to agents table
- Updated API response format

### Actions Required
- Update API clients to handle new fields
- Test integration with new format

### Rollback Plan
- Automatic rollback if migration fails
- Manual rollback available via admin dashboard
```

## Common Migration Patterns

### Add Column
```python
def upgrade():
    op.add_column(
        'table_name',
        sa.Column('new_col', sa.String(100), nullable=True)
    )
```

### Remove Column
```python
def upgrade():
    op.drop_column('table_name', 'old_col')
```

### Rename Column
```python
def upgrade():
    op.alter_column(
        'table_name',
        'old_name',
        new_column_name='new_name'
    )
```

### Add Index
```python
def upgrade():
    op.create_index(
        'ix_table_column',
        'table_name',
        ['column_name']
    )
```

### Data Transformation
```python
def upgrade():
    # Transform data
    op.execute("""
        UPDATE table_name
        SET column_name = UPPER(column_name)
        WHERE column_name IS NOT NULL
    """)
```

## Migration Tools

### Alembic
- Database migrations
- Schema versioning
- Rollback support

### Flyway
- Database migrations
- Multiple databases
- Team collaboration

### Liquibase
- Database migrations
- XML/YAML/JSON changelogs
- Complex transformations

## Gotchas

1. **Always backup** before migration
2. **Test on staging** first
3. **Write reversible migrations**
4. **Handle data carefully**
5. **Use transactions** for atomic changes
6. **Document breaking changes**
7. **Monitor migration progress**
8. **Verify after migration**
9. **Have rollback plan ready**
10. **Communicate with stakeholders**

## Best Practices

1. Keep migrations small and focused
2. Test migrations thoroughly
3. Use version control for migrations
4. Document migration procedures
5. Monitor migration performance
6. Have rollback procedures ready
7. Communicate changes clearly
8. Validate after migration
9. Clean up old migrations periodically
10. Use automated migration tools
