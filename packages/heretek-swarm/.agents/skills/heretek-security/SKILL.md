---
name: heretek-security
description: >-
  Security practices for Heretek Swarm. Use when implementing authentication,
  working with secrets, configuring NATS mTLS, or reviewing code for security
  issues. Covers zero-trust architecture, input validation, and audit trails.
---

# Heretek Swarm Security

## Security Architecture

### Zero-Trust Model
- **All inter-agent messages authenticated**
- **No implicit trust** between services
- **Least privilege** access principles
- **Defense in depth** with multiple layers

### Security Layers
1. **Network** - mTLS everywhere
2. **Authentication** - API keys, JWTs
3. **Authorization** - Role-based access
4. **Input Validation** - Sanitize all inputs
5. **Audit Trails** - Log all operations
6. **Secrets Management** - SOPS encryption
7. **Rate Limiting** - slowapi (Phase 1.5)
8. **Immune Response** - anomaly detection (security/immune)

### Security Package Layout (Phase 0.5 + 1.5 + 2.5 + 2.10)

```
backend/heretek_swarm/security/
├── auth.py             # TokenStore (Phase 2.10 — single source of truth)
├── rate_limiter.py     # slowapi wrapper (Phase 1.5 — canonical entry)
├── immune.py           # 58-LOC re-export shim → immune_types + immune_engine
├── immune_types.py     # 4 enums + 6 dataclasses (Phase 2.11)
├── immune_engine.py    # ImmuneResponseBuilding + ImmuneResponseEngine
├── behavioral_baseline.py
├── zero_trust.py
├── api_keys.py
├── jwt.py
└── sops_secrets.py
```

## Authentication

### TokenStore (Phase 2.10 — canonical)

The audit (§1.7) flagged that three different `*AuthManager`
classes (`gateway.auth.verify_auth`, `api.consensus.ConsensusAuthManager`,
`api.websockets.WebSocketAuthManager`) issued and validated tokens
with subtle semantic drift. Phase 2.10 consolidated them.

```python
from heretek_swarm.gateway.auth import TokenStore, default_token_store

# Process-wide canonical store
store: TokenStore = default_token_store

# Generate / validate / revoke
token = store.generate_token(user_id="user-1", roles=["admin"])
is_valid = store.validate_token(token)
store.revoke_token(token)
store.check_permission(token, "agent.terminate")
```

`ConsensusAuthManager` and `WebSocketAuthManager` are now thin
shims that delegate to the canonical `TokenStore`. A token issued
by the consensus auth manager is visible to the WebSocket auth
manager (and vice versa) — that is the intended behavior (single
source of trust for the whole process).

### Rate Limiting (Phase 1.5)

The audit (§3.1) flagged the hand-rolled `RateLimiter` in
`security/ddos_protection.py` as a reimplementation of slowapi. The
canonical entry is now `security/rate_limiter.py`:

```python
from heretek_swarm.security.rate_limiter import limiter, install_rate_limiter

# limiter is a slowapi.Limiter (MovingWindow strategy)
# install_rate_limiter(app) wires it into the FastAPI app

from fastapi import FastAPI
app = FastAPI()
install_rate_limiter(app)

# Per-route limits
@app.get("/api/something")
@limiter.limit("100/minute")
async def something(request: Request):
    ...
```

The legacy `InMemoryRateLimiter` + `RateLimitMiddleware` in
`api/rate_limiting.py` are kept for backwards compat; the
`security/ddos_protection.RateLimiter` stays for DDoS-pattern
detection (sliding window, geo-anomaly, mitigation) which slowapi
does not provide.

### Immune Response Engine (Phase 2.11)

The immune-response engine was misfiled under `consensus/immune.py`
(it's anomaly detection, not a consensus algorithm). Phase 2.11
moved it to `security/`:

```python
from heretek_swarm.security.immune import (
    ImmuneResponseBuilding,      # the immune-system analogy
    ImmuneResponseEngine,         # Sentinel's anomaly learning
    ImmunePattern,                # antigen
    NovelPatternPreservation,     # antibody for human review
)

# Old import path is preserved as a 42-LOC re-export shim:
from heretek_swarm.consensus.immune import ImmuneResponseBuilding  # still works
```

## Authentication (legacy)

### API Keys
```python
# backend/heretek_swarm/security/api_keys.py
from heretek_swarm.security import verify_api_key

@router.get("/agents")
async def get_agents(api_key: str = Depends(verify_api_key)):
    # API key verified
    return await list_agents()
```

### JWT Tokens
```python
# backend/heretek_swarm/security/jwt.py
from heretek_swarm.security import create_token, verify_token

# Create token
token = create_token(
    user_id="user123",
    roles=["admin"],
    expires_in=timedelta(hours=1)
)

# Verify token
payload = verify_token(token)
```

### Agent Authentication
```python
# All agent messages must be authenticated
class AgentMessage:
    content: str
    sender: str
    recipient: str
    signature: str  # HMAC signature
    timestamp: datetime

    def verify(self) -> bool:
        """Verify message signature."""
        return verify_hmac(
            self.content,
            self.signature,
            get_agent_key(self.sender)
        )
```

## NATS mTLS

### Certificate Generation
```bash
# Generate certificates
cd certs
./generate.sh

# Files created:
# - ca.pem (Certificate Authority)
# - server.pem (Server certificate)
# - server.key (Server private key)
# - client.pem (Client certificate)
# - client.key (Client private key)
```

### Configuration
```yaml
# docker-compose.yml
services:
  nats:
    command: >
      --tls
      --tls_cert=/certs/server.pem
      --tls_key=/certs/server.key
      --tls_ca=/certs/ca.pem
      --tls_verify=true
```

### Client Connection
```python
# backend/heretek_swarm/gateway/nats_client.py
import nats

async def connect_nats():
    nc = await nats.connect(
        "nats://nats:4222",
        tls={
            "cert": "/certs/client.pem",
            "key": "/certs/client.key",
            "ca": "/certs/ca.pem"
        }
    )
    return nc
```

## Input Validation

### Pydantic Models
```python
from pydantic import BaseModel, Field, validator

class AgentMessage(BaseModel):
    content: str = Field(..., max_length=10000)
    recipient: str = Field(..., pattern=r'^[a-z_]+$')

    @validator('content')
    def sanitize_content(cls, v):
        # Remove potentially dangerous content
        return sanitize_input(v)
```

### FastAPI Validation
```python
from fastapi import HTTPException, Query

@router.get("/search")
async def search(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=100)
):
    # Query validated
    return await search_memories(query, limit)
```

### Agent Message Validation
```python
# backend/heretek_swarm/security/zero_trust.py
class ZeroTrustValidator:
    def validate_message(self, message: AgentMessage) -> bool:
        # Validate signature
        if not message.verify():
            raise InvalidSignature()

        # Validate timestamp (within 5 minutes)
        if abs((datetime.now() - message.timestamp).total_seconds()) > 300:
            raise MessageExpired()

        # Validate sender exists
        if not agent_exists(message.sender):
            raise UnknownAgent()

        return True
```

## Secrets Management

### SOPS Encryption
```bash
# Encrypt secrets
sops --encrypt secrets/decrypted.env > secrets/encrypted.env

# Decrypt secrets
sops --decrypt secrets/encrypted.env > secrets/decrypted.env

# Edit encrypted file
sops secrets/encrypted.env
```

### Environment Variables
```bash
# Never commit secrets
# Use .env.example as template
cp .env.example .env

# Load secrets in Docker
docker compose --env-file secrets/decrypted.env up
```

### Secret Rotation
```bash
# Rotate API keys
./scripts/rotate_keys.sh

# Rotate database passwords
./scripts/rotate_db_password.sh

# Rotate NATS certificates
./scripts/rotate_nats_certs.sh
```

## Audit Trails

### Structured Logging
```python
import structlog

logger = structlog.get_logger(__name__)

# Log security events
logger.info(
    "agent_message_sent",
    sender="explorer",
    recipient="coordinator",
    message_type="status",
    timestamp=datetime.now().isoformat()
)

# Log authentication attempts
logger.warning(
    "authentication_failed",
    api_key_prefix="sk-...",
    ip_address="192.168.1.100",
    reason="invalid_key"
)
```

### Audit Database
```sql
-- Audit table
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    details JSONB,
    ip_address INET,
    user_agent TEXT
);

-- Index for fast queries
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_actor ON audit_log(actor);
```

### Compliance Logging
```python
# Log all data access
@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str, user: User = Depends(get_current_user)):
    memory = await get_memory_by_id(memory_id)

    # Audit log
    await audit_log(
        action="memory_accessed",
        actor=user.id,
        resource=memory_id,
        details={"tags": memory.tags}
    )

    return memory
```

## Authorization

### Role-Based Access
```python
from enum import Enum

class Role(Enum):
    ADMIN = "admin"
    AGENT = "agent"
    USER = "user"

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

# Check permissions
def check_permission(user: User, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[user.role]
```

### Agent Permissions
```python
# Define agent capabilities
AGENT_CAPABILITIES = {
    "explorer": ["read", "write", "search"],
    "coder": ["read", "write", "execute"],
    "sentinel": ["read", "monitor", "alert"],
    "arbiter": ["read", "write", "decide"]
}

def check_agent_permission(agent: str, action: str) -> bool:
    return action in AGENT_CAPABILITIES.get(agent, [])
```

## Rate Limiting

### Implementation
```python
from heretek_swarm.security.rate_limiter import RateLimiter

# Global rate limiter
rate_limiter = RateLimiter(
    max_requests=1000,
    window_seconds=60
)

# Per-agent rate limiter
agent_rate_limiter = RateLimiter(
    max_requests=100,
    window_seconds=60,
    key_func=lambda: current_agent.id
)

@router.get("/agents")
async def get_agents():
    if not rate_limiter.allow():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await list_agents()
```

### Rate Limit Headers
```python
@router.get("/agents")
async def get_agents():
    return JSONResponse(
        content=agents,
        headers={
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "95",
            "X-RateLimit-Reset": "1640995200"
        }
    )
```

## Security Testing

### Static Analysis
```bash
# Bandit (Python security linter)
bandit -r backend/

# Safety (dependency vulnerabilities)
safety check

# Semgrep
semgrep --config=auto backend/
```

### Dynamic Testing
```bash
# OWASP ZAP
docker run -t owasp/zap2docker-stable zap-full-scan.py http://localhost:8000

# Nmap
nmap -sV --script vuln localhost
```

### Penetration Testing
```bash
# SQL injection testing
sqlmap -u "http://localhost:8000/api/search?query=test" --batch

# XSS testing
# Manual testing with browser dev tools
```

## Code Review Security Checklist

### Input Validation
- [ ] All inputs validated with Pydantic
- [ ] SQL queries use parameterized queries
- [ ] File paths validated to prevent traversal
- [ ] User input sanitized before display

### Authentication
- [ ] API keys verified on all endpoints
- [ ] JWT tokens validated properly
- [ ] Agent messages authenticated
- [ ] No hardcoded credentials

### Authorization
- [ ] Role-based access control implemented
- [ ] Least privilege principle applied
- [ ] Sensitive operations logged
- [ ] Admin endpoints protected

### Secrets
- [ ] No secrets in code
- [ ] Secrets encrypted at rest
- [ ] Secrets rotated regularly
- [ ] Access to secrets logged

### Error Handling
- [ ] Errors don't leak sensitive info
- [ ] Stack traces not exposed
- [ ] Validation errors generic
- [ ] Rate limiting implemented

## Security Monitoring

### Alert Rules
```yaml
# prometheus/alerts.yml
groups:
  - name: security
    rules:
      - alert: HighFailedLogins
        expr: rate(failed_logins_total[5m]) > 10
        labels:
          severity: warning

      - alert: UnauthorizedAccess
        expr: increase(unauthorized_access_total[1h]) > 5
        labels:
          severity: critical
```

### Dashboard
```python
# Grafana dashboard for security metrics
- Failed login attempts
- Rate limit violations
- Unauthorized access attempts
- Audit log activity
- Certificate expiration
```

## Incident Response

### Security Incident Checklist
1. **Detect** - Identify the incident
2. **Contain** - Limit damage
3. **Eradicate** - Remove threat
4. **Recover** - Restore systems
5. **Learn** - Post-mortem analysis

### Emergency Procedures
```bash
# Revoke all API keys
./scripts/revoke_all_keys.sh

# Rotate all secrets
./scripts/rotate_all_secrets.sh

# Enable maintenance mode
./scripts/maintenance_mode.sh on

# Review audit logs
docker compose exec postgres psql -U postgres -c \
  "SELECT * FROM audit_log WHERE timestamp > now() - interval '1 hour' ORDER BY timestamp DESC;"
```

## Gotchas

1. **Never commit secrets** - Use SOPS encryption
2. **Always validate inputs** - SQL injection, XSS, path traversal
3. **Authenticate all messages** - Zero-trust model
4. **Log security events** - Audit trails required
5. **Rotate secrets regularly** - Automate rotation
6. **Monitor for anomalies** - Set up alerts
7. **Test security regularly** - Penetration testing
8. **Keep dependencies updated** - Vulnerability scanning
9. **Use HTTPS everywhere** - TLS termination
10. **Follow least privilege** - Minimal access rights

## Best Practices

1. Implement defense in depth
2. Use parameterized queries
3. Validate all inputs
4. Implement proper error handling
5. Use secure defaults
6. Keep security logs
7. Rotate secrets regularly
8. Monitor for suspicious activity
9. Conduct regular security reviews
10. Document security procedures
