---
name: heretek-docker-operations
description: >-
  Docker and container operations for Heretek Swarm. Use when working with
  Docker Compose, building images, managing services, or debugging container
  issues. Covers development, staging, and production configurations.
---

# Heretek Swarm Docker Operations

## Architecture

### Services
```yaml
# docker-compose.yml
services:
  api:           # FastAPI backend
  dashboard:     # React frontend
  nats:          # Message broker (with mTLS)
  postgres:      # Primary database
  redis:         # Cache layer
  qdrant:        # Vector database
```

### Ports
- **API**: 8000 (HTTP), 8001 (gRPC)
- **Dashboard**: 5173 (dev), 80 (prod)
- **NATS**: 4222 (client), 8222 (monitoring)
- **PostgreSQL**: 5432
- **Redis**: 6379
- **Qdrant**: 6333

## Development Setup

### Prerequisites
- Docker Desktop 4.x
- Docker Compose v2.x
- 8GB+ RAM allocated to Docker

### Quick Start
```bash
# Clone and setup
git clone <repo-url>
cd heretek-swarm

# Copy environment template
cp .env.example .env

# Start all services
docker compose up

# Detached mode
docker compose up -d

# View logs
docker compose logs -f api
```

### Initial Setup
```bash
# Run migrations
docker compose exec api python scripts/run_migrations.py

# Seed test data
docker compose exec api python scripts/seed_data.py

# Generate NATS certs
cd certs && ./generate.sh
```

## Common Commands

### Service Management
```bash
# Start specific service
docker compose up nats postgres

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Restart a service
docker compose restart api

# View running containers
docker compose ps
```

### Logs and Debugging
```bash
# Follow all logs
docker compose logs -f

# Specific service logs
docker compose logs -f api

# Last 100 lines
docker compose logs --tail 100 api

# View container stats
docker stats
```

### Executing Commands
```bash
# Run command in container
docker compose exec api python scripts/run_migrations.py

# Interactive shell
docker compose exec api bash

# Run one-off command
docker compose run --rm api python scripts/seed_data.py
```

## Building Images

### Development Build
```bash
# Build all services
docker compose build

# Build specific service
docker compose build api

# No cache build
docker compose build --no-cache api
```

### Production Build
```bash
# Multi-stage build
docker build -t heretek-swarm:latest .

# Tag for registry
docker tag heretek-swarm:latest registry.example.com/heretek-swarm:latest

# Push to registry
docker push registry.example.com/heretek-swarm:latest
```

### Dockerfile Patterns
```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev

FROM python:3.11-slim as runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY backend/ /app/backend/
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "heretek_swarm.api.main"]
```

## Database Operations

### PostgreSQL
```bash
# Connect to database
docker compose exec postgres psql -U postgres -d heretek_swarm

# Run migrations
docker compose exec api python scripts/run_migrations.py

# Backup database
docker compose exec postgres pg_dump -U postgres heretek_swarm > backup.sql

# Restore database
docker compose exec -T postgres psql -U postgres heretek_swarm < backup.sql
```

### Redis
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Flush all data
docker compose exec redis redis-cli FLUSHALL

# Monitor commands
docker compose exec redis redis-cli MONITOR
```

### Qdrant
```bash
# Check collections
curl http://localhost:6333/collections

# Create collection
curl -X PUT http://localhost:6333/collections/memories \
  -H 'Content-Type: application/json' \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

## NATS Configuration

### mTLS Setup
```bash
# Generate certificates
cd certs
./generate.sh

# Verify certs
openssl verify -CAfile ca.pem server.pem
```

### JetStream
```bash
# Check streams
nats stream ls

# Create stream
nats stream add EVENTS \
  --subjects="events.>" \
  --storage=file \
  --retention=limits \
  --max-msgs=1000000

# Publish test message
nats pub events.test "Hello World"
```

### Monitoring
```bash
# NATS monitoring endpoint
curl http://localhost:8222/varz

# Connection stats
curl http://localhost:8222/connz

# Route stats
curl http://localhost:8222/routez
```

## Environment Variables

### Required Variables
```bash
# .env
DATABASE_URL=postgresql://postgres:password@postgres:5432/heretek_swarm
REDIS_URL=redis://redis:6379
NATS_URL=nats://nats:4222
QDRANT_URL=http://qdrant:6333
OPENAI_API_KEY=sk-...
HERETEK_API_KEY=...
```

### Development vs Production
```bash
# Development
DEBUG=true
LOG_LEVEL=DEBUG
RELOAD=true

# Production
DEBUG=false
LOG_LEVEL=INFO
RELOAD=false
WORKERS=4
```

## Health Checks

### Service Health
```bash
# API health
curl http://localhost:8000/health

# Detailed health
curl http://localhost:8000/health/detailed

# Docker health check
docker compose ps  # Shows health status
```

### Custom Health Checks
```python
# backend/heretek_swarm/api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "services": {
            "database": await check_database(),
            "redis": await check_redis(),
            "nats": await check_nats(),
            "qdrant": await check_qdrant()
        }
    }
```

## Debugging

### Common Issues

1. **Port already in use**
   ```bash
   # Find process using port
   lsof -i :8000

   # Kill process
   kill -9 <PID>
   ```

2. **Container won't start**
   ```bash
   # Check logs
   docker compose logs api

   # Check environment
   docker compose exec api env
   ```

3. **Database connection refused**
   ```bash
   # Check if postgres is running
   docker compose ps postgres

   # Test connection
   docker compose exec postgres psql -U postgres
   ```

4. **NATS connection failed**
   ```bash
   # Check certs
   ls -la certs/

   # Verify cert validity
   openssl x509 -in certs/server.pem -text -noout
   ```

### Debug Commands
```bash
# Inspect container
docker inspect heretek-swarm-api-1

# View container processes
docker top heretek-swarm-api-1

# Execute debug script
docker compose exec api python scripts/debug.py

# Capture network traffic
docker compose exec nats tcpdump -i eth0 -w /tmp/nats.pcap
```

## Performance Tuning

### Resource Limits
```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Caching
```yaml
services:
  api:
    volumes:
      - ./cache:/app/cache
    environment:
      - CACHE_DIR=/app/cache
```

### Scaling
```bash
# Scale API service
docker compose up --scale api=3

# Load balancer config
docker compose up nginx
```

## Security

### Secrets Management
```bash
# Use Docker secrets
docker secret create db_password ./secrets/db_password.txt

# In compose file
services:
  api:
    secrets:
      - db_password
secrets:
  db_password:
    file: ./secrets/db_password.txt
```

### Network Security
```yaml
# Network isolation
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true

services:
  nginx:
    networks:
      - frontend
  api:
    networks:
      - frontend
      - backend
```

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/docker.yml
name: Docker Build
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t heretek-swarm:test .

      - name: Run tests
        run: |
          docker compose up -d
          sleep 30
          curl -f http://localhost:8000/health
          docker compose down
```

## Backup and Recovery

### Backup Strategy
```bash
# Backup databases
docker compose exec postgres pg_dump -U postgres heretek_swarm > pg_backup.sql
docker compose exec redis redis-cli BGSAVE

# Backup volumes
docker run --rm -v heretek-swarm_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data

# Automated backup script
./scripts/backup.sh
```

### Recovery
```bash
# Restore PostgreSQL
docker compose exec -T postgres psql -U postgres heretek_swarm < pg_backup.sql

# Restore Redis
docker compose cp redis_backup.rdb redis:/data/dump.rdb
docker compose restart redis
```

## Gotchas

1. **Always run migrations first** - Container entrypoint runs migrations automatically
2. **NATS certs expire** - Regenerate when docker network changes
3. **Volume permissions** - Use correct user/group IDs
4. **Resource limits** - Set memory limits to prevent OOM
5. **Health checks** - Add health checks for all services
6. **Log rotation** - Configure log rotation in production
7. **Backup regularly** - Automate database backups
8. **Monitor resources** - Watch CPU/memory usage
9. **Use .dockerignore** - Exclude unnecessary files
10. **Clean up regularly** - Remove unused images/volumes

## Best Practices

1. Use multi-stage builds for smaller images
2. Minimize layers in Dockerfiles
3. Use specific base image tags (not `latest`)
4. Implement health checks
5. Set resource limits
6. Use Docker secrets for sensitive data
7. Implement proper logging
8. Use Docker Compose profiles for different environments
9. Keep containers stateless
10. Document service dependencies
