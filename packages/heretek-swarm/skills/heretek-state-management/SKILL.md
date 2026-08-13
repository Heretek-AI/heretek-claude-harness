---
name: heretek-state-management
description: >-
  State management for Heretek Swarm. Use when working with PostgreSQL, Redis,
  or Qdrant. Covers database operations, caching strategies, and vector search
  patterns.
---

# Heretek Swarm State Management

## Architecture Overview

### Storage Systems
- **PostgreSQL** - Primary database (relational data)
- **Redis** - Cache layer (fast access)
- **Qdrant** - Vector database (semantic search)

### Data Flow
```
Application → Redis (cache) → PostgreSQL (primary)
                ↓
            Qdrant (vectors)
```

## PostgreSQL

### Connection
```python
import asyncpg

async def get_pool():
    pool = await asyncpg.create_pool(
        "postgresql://postgres:password@postgres:5432/heretek_swarm",
        min_size=5,
        max_size=20
    )
    return pool
```

### Basic Operations
```python
# Query
async def get_agents(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM agents WHERE status = $1", "active")
        return rows

# Insert
async def create_agent(pool, agent_data):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agents (id, name, status, created_at)
            VALUES ($1, $2, $3, NOW())
        """, agent_data["id"], agent_data["name"], "active")

# Update
async def update_agent(pool, agent_id, updates):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE agents SET name = $1, updated_at = NOW()
            WHERE id = $2
        """, updates["name"], agent_id)

# Delete
async def delete_agent(pool, agent_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE id = $1", agent_id)
```

### Transactions
```python
async def transfer_task(pool, from_agent, to_agent, task_id):
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Update task assignment
            await conn.execute("""
                UPDATE tasks SET agent_id = $1 WHERE id = $2
            """, to_agent, task_id)

            # Update agent task counts
            await conn.execute("""
                UPDATE agents SET task_count = task_count - 1 WHERE id = $1
            """, from_agent)

            await conn.execute("""
                UPDATE agents SET task_count = task_count + 1 WHERE id = $1
            """, to_agent)
```

### Connection Pooling
```python
# Custom pool configuration
pool = await asyncpg.create_pool(
    dsn="postgresql://...",
    min_size=5,
    max_size=20,
    max_inactive_connection_lifetime=300,
    command_timeout=60,
    statement_cache_size=100,
    max_cached_statement_lifetime=300
)
```

## Redis

### Connection
```python
import redis.asyncio as redis

async def get_redis():
    r = redis.Redis(
        host="redis",
        port=6379,
        db=0,
        decode_responses=True
    )
    return r
```

### Basic Operations
```python
# String operations
async def cache_agent(r, agent_id, agent_data):
    await r.setex(
        f"agent:{agent_id}",
        3600,  # TTL in seconds
        json.dumps(agent_data)
    )

async def get_cached_agent(r, agent_id):
    data = await r.get(f"agent:{agent_id}")
    if data:
        return json.loads(data)
    return None

# Hash operations
async def cache_agent_hash(r, agent_id, agent_data):
    await r.hset(f"agent:{agent_id}", mapping=agent_data)
    await r.expire(f"agent:{agent_id}", 3600)

async def get_agent_hash(r, agent_id):
    return await r.hgetall(f"agent:{agent_id}")

# List operations
async def add_to_queue(r, queue_name, item):
    await r.rpush(f"queue:{queue_name}", json.dumps(item))

async def pop_from_queue(r, queue_name):
    data = await r.lpop(f"queue:{queue_name}")
    if data:
        return json.loads(data)
    return None

# Set operations
async def add_to_set(r, set_name, item):
    await r.sadd(f"set:{set_name}", json.dumps(item))

async def get_set_members(r, set_name):
    members = await r.smembers(f"set:{set_name}")
    return [json.loads(m) for m in members]
```

### Caching Patterns
```python
# Cache-aside pattern
async def get_agent_cached(r, pool, agent_id):
    # Try cache first
    cached = await get_cached_agent(r, agent_id)
    if cached:
        return cached

    # Cache miss - fetch from database
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agents WHERE id = $1",
            agent_id
        )

    if row:
        agent_data = dict(row)
        # Store in cache
        await cache_agent(r, agent_id, agent_data)
        return agent_data

    return None

# Write-through pattern
async def update_agent_cached(r, pool, agent_id, updates):
    # Update database
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE agents SET name = $1, updated_at = NOW()
            WHERE id = $2
        """, updates["name"], agent_id)

    # Update cache
    agent_data = await get_agent_cached(r, pool, agent_id)
    if agent_data:
        agent_data.update(updates)
        await cache_agent(r, agent_id, agent_data)
```

### Pub/Sub
```python
# Publisher
async def publish_event(r, event_type, data):
    await r.publish(f"events:{event_type}", json.dumps(data))

# Subscriber
async def subscribe_events(r, event_type, handler):
    pubsub = r.pubsub()
    await pubsub.subscribe(f"events:{event_type}")

    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await handler(data)
```

## Qdrant

### Connection
```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

def get_qdrant():
    client = QdrantClient(host="qdrant", port=6333)
    return client
```

### Collection Management
```python
async def create_collection(client, collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1536,  # OpenAI embedding size
            distance=Distance.COSINE
        )
    )

async def list_collections(client):
    return client.get_collections()
```

### Vector Operations
```python
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

async def upsert_vector(client, collection_name, point_id, vector, payload):
    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
        ]
    )

async def search_vectors(client, collection_name, query_vector, limit=10):
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit
    )
    return results

async def search_with_filter(client, collection_name, query_vector, agent_id, limit=10):
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="agent_id",
                    match=MatchValue(value=agent_id)
                )
            ]
        ),
        limit=limit
    )
    return results
```

### Semantic Search
```python
async def semantic_search(client, collection_name, query, embeddings, limit=10):
    # Generate query embedding
    query_vector = await embeddings.embed_query(query)

    # Search
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit
    )

    return [result.payload for result in results]
```

## Combined Patterns

### Multi-Layer Cache
```python
async def get_agent_multi_cache(redis_client, qdrant_client, pool, agent_id):
    # Layer 1: Redis cache
    cached = await get_cached_agent(redis_client, agent_id)
    if cached:
        return cached

    # Layer 2: Database
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agents WHERE id = $1",
            agent_id
        )

    if row:
        agent_data = dict(row)
        await cache_agent(redis_client, agent_id, agent_data)
        return agent_data

    return None
```

### Vector + Relational
```python
async def search_memories(qdrant_client, pool, query, agent_id, limit=10):
    # Vector search for semantic similarity
    query_vector = await embeddings.embed_query(query)

    vector_results = qdrant_client.search(
        collection_name="memories",
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="agent_id",
                    match=MatchValue(value=agent_id)
                )
            ]
        ),
        limit=limit
    )

    # Get full records from PostgreSQL
    memory_ids = [r.id for r in vector_results]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM memories WHERE id = ANY($1)",
            memory_ids
        )

    return rows
```

## Performance Optimization

### Connection Pooling
```python
# PostgreSQL
pool = await asyncpg.create_pool(
    dsn="postgresql://...",
    min_size=5,
    max_size=20
)

# Redis
redis_pool = redis.ConnectionPool.from_url(
    "redis://redis:6379",
    max_connections=20
)
```

### Caching Strategies
```python
# TTL-based caching
async def cache_with_ttl(r, key, value, ttl=3600):
    await r.setex(key, ttl, json.dumps(value))

# Write-behind caching
async def write_behind(r, pool, key, value):
    await r.set(key, json.dumps(value))
    # Async write to database
    asyncio.create_task(write_to_db(pool, key, value))
```

### Batch Operations
```python
# Batch insert
async def batch_insert(pool, records):
    async with pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO agents (id, name) VALUES ($1, $2)",
            [(r["id"], r["name"]) for r in records]
        )

# Batch cache
async def batch_cache(r, items):
    pipe = r.pipeline()
    for item in items:
        pipe.setex(
            f"item:{item['id']}",
            3600,
            json.dumps(item)
        )
    await pipe.execute()
```

## Monitoring

### Health Checks
```python
async def check_postgres(pool):
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False

async def check_redis(r):
    try:
        await r.ping()
        return True
    except Exception:
        return False

async def check_qdrant(client):
    try:
        client.get_collections()
        return True
    except Exception:
        return False
```

### Metrics
```python
# Track cache hit rate
class CacheMetrics:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def hit(self):
        self.hits += 1

    def miss(self):
        self.misses += 1

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0
```

## Gotchas

1. **Connection limits** - Don't exhaust connection pools
2. **Cache invalidation** - Hard problem, plan for it
3. **Vector dimensions** - Must match embedding model
4. **Transaction scope** - Keep transactions short
5. **TTL alignment** - Cache TTL should match data freshness needs
6. **Batch sizes** - Don't send too many operations at once
7. **Error handling** - Retry logic for transient failures
8. **Monitoring** - Track cache hit rates and query performance

## Best Practices

1. Use connection pooling
2. Implement caching layers
3. Monitor performance metrics
4. Handle failures gracefully
5. Use transactions for consistency
6. Optimize queries with indexes
7. Batch operations when possible
8. Clean up old data regularly
9. Test with production-like data
10. Document data schemas
