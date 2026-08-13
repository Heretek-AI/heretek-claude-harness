---
applyTo: "**/*"
---

# Agent Safety Governance Patterns for Heretek Swarm

## Tool Allowlisting
- All agent tools MUST be explicitly registered in the tool registry
- No dynamic tool creation at runtime
- Tool capabilities must be declared in agent manifest

## Content Filters
- All agent outputs must pass content safety filters
- PII detection required on all user-facing outputs
- Rate limiting enforced per-agent and per-user

## Audit Trails
- All agent decisions must be logged to append-only audit store
- Include: timestamp, agent ID, input hash, decision, confidence score
- Audit logs must be immutable and queryable

## Input Validation
- Validate ALL inputs against JSON Schema before processing
- Reject inputs exceeding size limits (default: 1MB)
- Sanitize file paths and URLs

## Zero-Trust Architecture
- Authenticate every inter-agent message
- mTLS required for all NATS communication
- JWT tokens must have expiration and scope limits
- No implicit trust between agents

## Rate Limiting
- Per-agent rate limits on message processing
- Circuit breakers on external API calls
- Backpressure handling for message queues

## Secrets Management
- Never hardcode secrets in agent code
- Use SOPS-encrypted files for configuration
- Rotate API keys on a schedule
