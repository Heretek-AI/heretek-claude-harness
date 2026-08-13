---
name: heretek-debugging
description: >-
  Debugging and troubleshooting patterns for Heretek Swarm. Use when diagnosing
  issues, investigating failures, or optimizing performance. Covers logging,
  profiling, and common problem patterns.
---

# Heretek Swarm Debugging

## Debugging Philosophy

### Principles
1. **Reproduce first** - Understand the issue before fixing
2. **Check logs** - Start with structured logs
3. **Isolate** - Narrow down the problem scope
4. **Verify** - Confirm the fix works
5. **Document** - Record what you learned

### Mindset
- Problems are puzzles to solve
- Stay curious, not frustrated
- Document findings for future reference
- Fix root causes, not symptoms

## Logging

### Structured Logging
```python
import structlog

logger = structlog.get_logger(__name__)

# Info level
logger.info(
    "agent_message_sent",
    sender="explorer",
    recipient="coordinator",
    message_type="status",
    timestamp=datetime.now().isoformat()
)

# Warning level
logger.warning(
    "rate_limit_approaching",
    agent="coder",
    current_rate=95,
    limit=100
)

# Error level
logger.error(
    "agent_message_failed",
    sender="explorer",
    recipient="coordinator",
    error=str(e),
    traceback=traceback.format_exc()
)
```

### Log Levels
```python
# DEBUG - Detailed information for debugging
logger.debug("processing_message", message_id=msg.id)

# INFO - General information
logger.info("agent_started", agent_name="explorer")

# WARNING - Unexpected situation
logger.warning("slow_query", duration=2.5, query="SELECT * FROM agents")

# ERROR - Failure that needs attention
logger.error("agent_failed", agent="explorer", error=str(e))

# CRITICAL - System cannot continue
logger.critical("database_connection_failed", error=str(e))
```

### Log Configuration
```python
# config/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)
```

## Debugging Tools

### Python Debugger
```python
# Set breakpoint
import pdb; pdb.set_trace()

# Or in Python 3.7+
breakpoint()

# Or better - use ipdb
import ipdb; ipdb.set_trace()
```

### Logging Debug
```python
# Temporary debug logging
logger.debug("state_check", variable=variable_name)

# Conditional debug
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("expensive_operation", result=expensive_call())
```

### HTTP Debugging
```python
# Enable HTTP debugging
import http.client
http.client.HTTPConnection.debuglevel = 1

# Or use httpx
client = httpx.AsyncClient()
response = await client.get(url)
print(response.request.url)
print(response.request.headers)
print(response.status_code)
print(response.text)
```

## Common Issues

### Database Issues

#### Connection Errors
```python
# Symptom: "connection refused" or "timeout"
# Check:
1. Database is running: docker compose ps postgres
2. Connection string is correct
3. Network connectivity
4. Connection pool not exhausted

# Debug:
async def debug_db_connection():
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("db_connection_ok")
    except Exception as e:
        logger.error("db_connection_failed", error=str(e))
```

#### Slow Queries
```python
# Symptom: High response times
# Check:
1. Query execution plan
2. Missing indexes
3. Table statistics
4. Connection pool size

# Debug:
import time

async def debug_query(pool, query):
    start = time.time()
    async with pool.acquire() as conn:
        result = await conn.fetch(query)
    duration = time.time() - start

    if duration > 1.0:
        logger.warning("slow_query", query=query, duration=duration)

    return result
```

### Memory Issues

#### Memory Leaks
```python
# Symptom: Increasing memory usage
# Check:
1. Object references
2. Cache growth
3. Connection pools
4. Task accumulation

# Debug:
import tracemalloc

tracemalloc.start()

# ... code to debug ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

#### Cache Bloat
```python
# Symptom: Redis memory growing
# Check:
1. TTL values
2. Cache key patterns
3. Eviction policy

# Debug:
async def debug_redis_memory(r):
    info = await r.info("memory")
    logger.info("redis_memory",
        used=info["used_memory_human"],
        peak=info["used_memory_peak_human"]
    )
```

### Message Queue Issues

#### NATS Connection
```python
# Symptom: Messages not received
# Check:
1. NATS is running
2. Subject names match
3. Queue groups configured
4. mTLS certificates valid

# Debug:
async def debug_nats_connection(nc):
    logger.info("nats_status",
        connected=nc.is_connected,
        url=nc.connected_url,
        stats=nc.stats
    )
```

#### Message Loss
```python
# Symptom: Missing messages
# Check:
1. JetStream enabled
2. Message acknowledgment
3. Consumer configuration
4. Stream retention

# Debug:
async def debug_nats_messages(nc):
    js = nc.jetstream()
    info = await js.stream_info("EVENTS")
    logger.info("nats_stream",
        messages=info.state.messages,
        bytes=info.state.bytes
    )
```

### Performance Issues

#### High CPU
```python
# Symptom: High CPU usage
# Check:
1. Infinite loops
2. Expensive calculations
3. Blocking I/O
4. Too many workers

# Debug:
import cProfile

profiler = cProfile.Profile()
profiler.enable()

# ... code to profile ...

profiler.disable()
profiler.print_stats(sort='cumtime')
```

#### Slow API Responses
```python
# Symptom: High response times
# Check:
1. Database queries
2. External API calls
3. Cache misses
4. Serialization overhead

# Debug:
from fastapi import Request
import time

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    if process_time > 1.0:
        logger.warning("slow_request",
            path=request.url.path,
            duration=process_time
        )

    return response
```

## Debugging Workflows

### Issue Investigation
```python
# Step 1: Reproduce
# Can you make the issue happen consistently?

# Step 2: Gather Information
# What are the symptoms?
# When did it start?
# What changed recently?

# Step 3: Isolate
# What component is affected?
# What's the minimal reproduction?

# Step 4: Diagnose
# Check logs
# Check metrics
# Check configuration

# Step 5: Fix
# Implement solution
# Test thoroughly

# Step 6: Verify
# Confirm fix works
# Monitor for regressions
```

### Log Analysis
```bash
# Find errors
grep -r "ERROR" logs/

# Find specific agent
grep "agent_name" logs/*.log | grep "ERROR"

# Find slow operations
grep "duration" logs/*.log | grep -E "duration[\":][0-9]+\.[0-9]" | sort -t: -k2 -n

# Find recent issues
find logs/ -name "*.log" -mmin -60 -exec grep "ERROR" {} \;
```

## Performance Profiling

### CPU Profiling
```python
import cProfile
import pstats

def profile_function(func):
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(10)

        return result
    return wrapper
```

### Memory Profiling
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # ... code to profile
    pass
```

### Async Profiling
```python
import asyncio
import time

async def profile_async():
    start = time.time()

    # ... async code ...

    duration = time.time() - start
    logger.info("async_profile", duration=duration)
```

## Monitoring

### Health Checks
```python
@router.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "nats": await check_nats(),
        "memory": await check_memory_usage()
    }

    healthy = all(checks.values())

    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks
    }
```

### Metrics Collection
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('api_requests_total', 'Total API requests')
REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'Request latency')

@router.get("/agents")
async def list_agents():
    with REQUEST_LATENCY.time():
        REQUEST_COUNT.inc()
        # ... endpoint logic
```

## Troubleshooting Checklist

### Application Won't Start
- [ ] Check environment variables
- [ ] Verify database connection
- [ ] Check port availability
- [ ] Review error logs
- [ ] Verify dependencies installed

### API Errors
- [ ] Check request format
- [ ] Verify authentication
- [ ] Check rate limits
- [ ] Review error response
- [ ] Check database state

### Performance Issues
- [ ] Profile CPU usage
- [ ] Check memory consumption
- [ ] Monitor database queries
- [ ] Review cache hit rates
- [ ] Check network latency

### Data Issues
- [ ] Verify data integrity
- [ ] Check migration status
- [ ] Review data transformations
- [ ] Validate business logic
- [ ] Check for race conditions

## Common Patterns

### Retry Logic
```python
async def retry_operation(func, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning("retrying_operation",
                attempt=attempt,
                error=str(e)
            )
            await asyncio.sleep(delay * (2 ** attempt))
```

### Circuit Breaker
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None

    async def call(self, func):
        if self.is_open():
            raise CircuitBreakerOpen()

        try:
            result = await func()
            self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def is_open(self):
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) < self.timeout
```

### Graceful Degradation
```python
async def get_agent_with_fallback(agent_id):
    try:
        # Try primary source
        return await get_from_database(agent_id)
    except DatabaseError:
        try:
            # Fallback to cache
            return await get_from_cache(agent_id)
        except CacheError:
            # Fallback to default
            return get_default_agent(agent_id)
```

## Gotchas

1. **Don't suppress errors** - Log them
2. **Use structured logging** - Easy to search
3. **Profile before optimizing** - Measure first
4. **Reproduce before fixing** - Understand the issue
5. **Test fixes thoroughly** - Don't introduce new bugs
6. **Document solutions** - Help future debugging
7. **Monitor in production** - Catch issues early
8. **Use breakpoints wisely** - Don't block production
9. **Clean up debug code** - Remove before committing
10. **Learn from incidents** - Post-mortem analysis

## Best Practices

1. Implement comprehensive logging
2. Use structured log formats
3. Monitor key metrics
4. Set up alerts for critical issues
5. Profile regularly
6. Test error scenarios
7. Document troubleshooting steps
8. Use debugging tools effectively
9. Clean up debug artifacts
10. Share learnings with team
