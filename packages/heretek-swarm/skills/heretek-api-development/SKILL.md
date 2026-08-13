---
name: heretek-api-development
description: >-
  API development patterns for Heretek Swarm FastAPI services. Use when creating
  new endpoints, implementing authentication, or working with API routers. Covers
  FastAPI patterns, OpenAPI documentation, and API testing.
---

# Heretek Swarm API Development

## Project Structure

```
backend/heretek_swarm/api/
├── __init__.py          # Router registration
├── main.py              # FastAPI app
├── dependencies.py      # Shared dependencies
├── routers/
│   ├── agents.py        # Agent endpoints
│   ├── memory.py        # Memory endpoints
│   ├── tasks.py         # Task endpoints
│   └── ...
├── schemas/
│   ├── agents.py        # Pydantic models
│   └── ...
└── middleware/
    ├── auth.py          # Authentication
    └── rate_limit.py    # Rate limiting
```

## Creating Endpoints

### Basic Endpoint
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    responses={404: {"description": "Not found"}}
)

class AgentResponse(BaseModel):
    id: str
    name: str
    status: str

@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    status: str = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all agents with optional filtering.

    - **status**: Filter by agent status
    - **limit**: Maximum number of agents to return
    """
    query = select(Agent)
    if status:
        query = query.where(Agent.status == status)
    query = query.limit(limit)

    result = await db.execute(query)
    agents = result.scalars().all()
    return agents
```

### Path Parameters
```python
@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific agent by ID.

    - **agent_id**: Unique agent identifier
    """
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} not found"
        )
    return agent
```

### Request Bodies
```python
class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    capabilities: List[str] = []
    metadata: dict = {}

@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(
    request: CreateAgentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new agent.

    - **name**: Agent name (required)
    - **capabilities**: List of agent capabilities
    - **metadata**: Additional metadata
    """
    agent = Agent(
        id=str(uuid4()),
        name=request.name,
        capabilities=request.capabilities,
        metadata=request.metadata
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent
```

### Query Parameters
```python
@router.get("/search")
async def search_agents(
    q: str = Query(..., min_length=1, max_length=100),
    tags: List[str] = Query(None),
    created_after: datetime = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Search agents with filters.

    - **q**: Search query (required)
    - **tags**: Filter by tags
    - **created_after**: Filter by creation date
    - **limit**: Maximum results
    """
    query = select(Agent).where(
        Agent.name.ilike(f"%{q}%")
    )

    if tags:
        query = query.where(Agent.tags.overlap(tags))
    if created_after:
        query = query.where(Agent.created_at > created_after)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

## Authentication

### API Key Authentication
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("HERETEK_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(
    api_key: str = Security(api_key_header)
):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key

@router.get("/protected")
async def protected_endpoint(
    api_key: str = Depends(verify_api_key)
):
    return {"message": "Access granted"}
```

### JWT Authentication
```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(
    token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user(user_id)
    if user is None:
        raise credentials_exception
    return user
```

## Error Handling

### Custom Exceptions
```python
class AgentNotFound(Exception):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")

class AgentConflict(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Agent with name {name} already exists")
```

### Exception Handlers
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AgentNotFound)
async def agent_not_found_handler(
    request: Request,
    exc: AgentNotFound
):
    return JSONResponse(
        status_code=404,
        content={
            "error": "agent_not_found",
            "detail": str(exc),
            "agent_id": exc.agent_id
        }
    )
```

### Validation Errors
```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors()
        }
    )
```

## Dependencies

### Database Session
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Current User
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    # ... authentication logic
    return user
```

### Rate Limiting
```python
from heretek_swarm.security.rate_limiter import RateLimiter

rate_limiter = RateLimiter(
    max_requests=100,
    window_seconds=60
)

async def check_rate_limit(
    api_key: str = Depends(verify_api_key)
):
    if not rate_limiter.allow(api_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
```

## OpenAPI Documentation

### Endpoint Documentation
```python
@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent by ID",
    description="Retrieve a specific agent using its unique identifier.",
    responses={
        200: {"description": "Agent found"},
        404: {"description": "Agent not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_agent(agent_id: str):
    # ...
```

### Schema Documentation
```python
class AgentResponse(BaseModel):
    """
    Agent response schema.

    Contains all agent information including metadata.
    """
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent display name")
    status: str = Field(..., description="Agent status")
    capabilities: List[str] = Field(
        default=[],
        description="List of agent capabilities"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
```

## Testing

### Unit Tests
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_agents():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/agents")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_agent():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/agents",
            json={"name": "Test Agent"}
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Test Agent"
```

### Integration Tests
```python
@pytest.mark.integration
async def test_agent_workflow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create agent
        create_response = await client.post(
            "/api/agents",
            json={"name": "Workflow Agent"}
        )
        agent_id = create_response.json()["id"]

        # Get agent
        get_response = await client.get(f"/api/agents/{agent_id}")
        assert get_response.status_code == 200

        # Update agent
        update_response = await client.put(
            f"/api/agents/{agent_id}",
            json={"name": "Updated Agent"}
        )
        assert update_response.status_code == 200
```

## Performance

### Caching
```python
from fastapi import Cache

@router.get("/{agent_id}")
@Cache(expire=300)
async def get_agent_cached(agent_id: str):
    # ... fetch agent
    return agent
```

### Pagination
```python
from fastapi import Query
from typing import List

@router.get("/")
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size

    query = select(Agent).offset(offset).limit(page_size)
    result = await db.execute(query)
    agents = result.scalars().all()

    # Get total count
    count_query = select(func.count(Agent.id))
    total = await db.execute(count_query)

    return {
        "items": agents,
        "total": total.scalar(),
        "page": page,
        "page_size": page_size,
        "pages": (total.scalar() + page_size - 1) // page_size
    }
```

## Gotchas

1. **Always validate inputs** - Use Pydantic models
2. **Handle errors properly** - Return meaningful error responses
3. **Use dependencies** - Don't repeat authentication logic
4. **Document endpoints** - OpenAPI docs are auto-generated
5. **Test thoroughly** - Unit and integration tests
6. **Use async/await** - All I/O should be async
7. **Implement rate limiting** - Protect against abuse
8. **Use proper HTTP methods** - GET, POST, PUT, DELETE
9. **Return appropriate status codes** - 200, 201, 400, 404, etc.
10. **Version your API** - Use URL prefixes or headers

## Best Practices

1. Follow RESTful conventions
2. Use consistent error formats
3. Implement proper authentication
4. Document all endpoints
5. Use type hints everywhere
6. Validate all inputs
7. Handle errors gracefully
8. Use dependency injection
9. Implement rate limiting
10. Test thoroughly
