---
name: heretek-nats-messaging
description: >-
  NATS messaging patterns for Heretek Swarm. Use when implementing inter-agent
  communication, working with JetStream, or debugging messaging issues. Covers
  pub/sub, request/reply, and queue groups.
---

# Heretek Swarm NATS Messaging

## Architecture

### Message Flow
```
Agent A → NATS → Agent B
         ↓
    JetStream (persistent)
         ↓
    Queue Groups (load balancing)
```

### Core Concepts
- **Publish/Subscribe** - Broadcast messages
- **Request/Reply** - Synchronous communication
- **Queue Groups** - Load balancing
- **JetStream** - Persistent messaging
- **Subjects** - Message routing

## Connection Setup

### Basic Connection
```python
import nats

async def connect_nats():
    nc = await nats.connect("nats://nats:4222")
    return nc
```

### mTLS Connection
```python
async def connect_nats_tls():
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

### Connection with Reconnect
```python
async def connect_nats_reliable():
    nc = await nats.connect(
        "nats://nats:4222",
        max_reconnect_attempts=10,
        reconnect_time_wait=2,
        error_cb=error_handler,
        disconnected_cb=disconnected_handler,
        reconnected_cb=reconnected_handler
    )
    return nc
```

## Publishing Messages

### Simple Publish
```python
async def publish_message(nc, subject, data):
    import json
    message = json.dumps(data)
    await nc.publish(subject, message.encode())
```

### Publish with Headers
```python
async def publish_with_headers(nc, subject, data, headers):
    import json
    message = json.dumps(data)
    await nc.publish(
        subject,
        message.encode(),
        headers=headers
    )
```

### Publish to JetStream
```python
async def publish_to_stream(nc, subject, data):
    import json
    message = json.dumps(data)
    ack = await nc.publish(subject, message.encode())
    return ack
```

## Subscribing to Messages

### Basic Subscription
```python
async def subscribe(nc, subject, callback):
    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        await callback(data)

    sub = await nc.subscribe(subject, cb=message_handler)
    return sub
```

### Subscription with Queue Group
```python
async def subscribe_queue(nc, subject, queue, callback):
    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        await callback(data)

    sub = await nc.subscribe(
        subject,
        queue=queue,
        cb=message_handler
    )
    return sub
```

### JetStream Subscription
```python
async def subscribe_jetstream(nc, subject, callback):
    js = nc.jetstream()

    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        await callback(data)
        await msg.ack()  # Acknowledge message

    sub = await js.subscribe(
        subject,
        cb=message_handler
    )
    return sub
```

## Request/Reply Pattern

### Request
```python
async def request_message(nc, subject, data, timeout=5):
    import json
    message = json.dumps(data)
    response = await nc.request(
        subject,
        message.encode(),
        timeout=timeout
    )
    return json.loads(response.data.decode())
```

### Reply
```python
async def reply_handler(nc, subject, handler):
    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        response = await handler(data)
        await msg.respond(json.dumps(response).encode())

    sub = await nc.subscribe(subject, cb=message_handler)
    return sub
```

## Agent Communication

### Direct Messaging
```python
class AgentMessenger:
    def __init__(self, nc, agent_id):
        self.nc = nc
        self.agent_id = agent_id

    async def send(self, recipient, content, message_type):
        subject = f"agents.{recipient}"
        message = {
            "sender": self.agent_id,
            "content": content,
            "type": message_type,
            "timestamp": datetime.now().isoformat()
        }
        await self.nc.publish(subject, json.dumps(message).encode())

    async def broadcast(self, content, message_type):
        subject = "agents.broadcast"
        message = {
            "sender": self.agent_id,
            "content": content,
            "type": message_type,
            "timestamp": datetime.now().isoformat()
        }
        await self.nc.publish(subject, json.dumps(message).encode())
```

### Request/Reply between Agents
```python
class AgentRequester:
    def __init__(self, nc, agent_id):
        self.nc = nc
        self.agent_id = agent_id

    async def request(self, recipient, content, timeout=5):
        subject = f"agents.{recipient}.request"
        message = {
            "sender": self.agent_id,
            "content": content,
            "type": "request",
            "timestamp": datetime.now().isoformat()
        }

        response = await self.nc.request(
            subject,
            json.dumps(message).encode(),
            timeout=timeout
        )

        return json.loads(response.data.decode())
```

## JetStream

### Creating Streams
```python
async def create_stream(nc, name, subjects):
    js = nc.jetstream()
    await js.add_stream(
        name=name,
        subjects=subjects
    )
```

### Stream Configuration
```python
async def configure_stream(nc):
    js = nc.jetstream()
    await js.add_stream(
        name="EVENTS",
        subjects=["events.>"],
        storage="file",
        retention="limits",
        max_msgs=1000000,
        max_bytes=1024*1024*1024,  # 1GB
        max_age=timedelta(days=7)
    )
```

### Consuming from Streams
```python
async def consume_stream(nc, stream, subject):
    js = nc.jetstream()

    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        # Process message
        await msg.ack()

    sub = await js.subscribe(
        subject,
        stream=stream,
        cb=message_handler
    )
    return sub
```

## Queue Groups

### Load Balancing
```python
# Multiple instances in same queue group
# Messages are distributed across instances

# Instance 1
sub1 = await nc.subscribe("tasks", queue="workers", cb=handler)

# Instance 2
sub2 = await nc.subscribe("tasks", queue="workers", cb=handler)

# Instance 3
sub3 = await nc.subscribe("tasks", queue="workers", cb=handler)
```

### Agent Queue Groups
```python
# Same agent type in different instances
async def setup_agent_queue(nc, agent_type, handler):
    subject = f"agents.{agent_type}"
    queue = f"queue_{agent_type}"

    sub = await nc.subscribe(
        subject,
        queue=queue,
        cb=handler
    )
    return sub
```

## Error Handling

### Connection Errors
```python
async def error_handler(e):
    print(f"Connection error: {e}")

async def disconnected_handler():
    print("Disconnected from NATS")

async def reconnected_handler():
    print("Reconnected to NATS")

nc = await nats.connect(
    "nats://nats:4222",
    error_cb=error_handler,
    disconnected_cb=disconnected_handler,
    reconnected_cb=reconnected_handler
)
```

### Message Processing Errors
```python
async def safe_handler(msg):
    try:
        data = json.loads(msg.data.decode())
        await process_message(data)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        # Don't ack - message will be redelivered
    except Exception as e:
        print(f"Processing error: {e}")
        # Ack to prevent redeliveries
        await msg.ack()
```

## Monitoring

### Connection Stats
```python
async def get_stats(nc):
    stats = {
        "out_bytes": nc.stats.out_bytes,
        "in_bytes": nc.stats.in_bytes,
        "out_msgs": nc.stats.out_msgs,
        "in_msgs": nc.stats.in_msgs,
        "reconnects": nc.stats.reconnects
    }
    return stats
```

### JetStream Stats
```python
async def get_stream_stats(nc):
    js = nc.jetstream()
    info = await js.stream_info("EVENTS")
    return {
        "messages": info.state.messages,
        "bytes": info.state.bytes,
        "first_seq": info.state.first_seq,
        "last_seq": info.state.last_seq
    }
```

## Testing

### Mock NATS
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_nats():
    nc = AsyncMock()
    nc.publish = AsyncMock()
    nc.subscribe = AsyncMock()
    return nc

@pytest.mark.asyncio
async def test_publish(mock_nats):
    await publish_message(mock_nats, "test", {"key": "value"})
    mock_nats.publish.assert_called_once()
```

### Integration Tests
```python
@pytest.mark.integration
async def test_agent_communication():
    nc = await nats.connect("nats://localhost:4222")

    received = []

    async def handler(msg):
        received.append(json.loads(msg.data.decode()))

    await nc.subscribe("test", cb=handler)
    await nc.publish("test", json.dumps({"key": "value"}).encode())

    await asyncio.sleep(0.1)
    assert len(received) == 1
```

## Debugging

### Common Issues

1. **Connection refused**
   - Check NATS is running
   - Verify port 4222 is accessible
   - Check firewall rules

2. **Messages not received**
   - Verify subject matches
   - Check queue group configuration
   - Ensure subscription is active

3. **JetStream messages lost**
   - Check stream configuration
   - Verify message acknowledgment
   - Monitor stream stats

4. **mTLS errors**
   - Verify certificates are valid
   - Check certificate expiration
   - Ensure CA is trusted

### Debug Commands
```bash
# Check NATS connections
nats connection ls

# Check streams
nats stream ls

# Check consumers
nats consumer ls

# Publish test message
nats pub test "Hello"

# Subscribe to subject
nats sub test
```

## Best Practices

1. Use meaningful subject names
2. Implement proper error handling
3. Use JetStream for critical messages
4. Monitor connection health
5. Test message handling thoroughly
6. Document message formats
7. Use queue groups for load balancing
8. Implement message deduplication
9. Log all message operations
10. Have fallback mechanisms
