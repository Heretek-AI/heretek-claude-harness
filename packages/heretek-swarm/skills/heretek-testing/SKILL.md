---
name: heretek-testing
description: >-
  Testing patterns for Heretek Swarm. Use when writing tests, setting up test
  infrastructure, or debugging test failures. Covers pytest, vitest, mocking
  strategies, and test organization.
---

# Heretek Swarm Testing

## Test Structure

### Python Tests
```
tests/
├── test_memory.py              # Memory system tests
├── test_memory_migration.py    # Migration tests
├── test_auth.py                # Authentication tests
├── test_agents/                # Agent-specific tests
├── test_api/                   # API endpoint tests
├── test_integrations/          # Integration tests
├── conftest.py                 # Shared fixtures
└── fixtures/                   # Test data
```

### Frontend Tests
```
swarm-dashboard/src/
├── __tests__/                  # Co-located tests
├── *.test.tsx                  # Test files
├── *.spec.ts                   # Spec files
└── mocks/                      # Mock data
```

## Python Testing

### Setup
```bash
# Install test dependencies
uv sync --group dev

# Or fallback
pip install -e ".[dev]"
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# Single file
pytest tests/test_memory.py -v

# Single test
pytest tests/test_memory.py::test_search -v

# With coverage
pytest tests/ --cov=heretek_swarm --cov-report=html

# Parallel execution
pytest tests/ -n auto
```

### Test Configuration
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
markers = [
    "slow: marks tests as slow",
    "integration: marks integration tests",
    "unit: marks unit tests",
]
```

### Writing Tests

#### Unit Tests
```python
import pytest
from heretek_swarm.memory import CogneeMemoryReader

@pytest.mark.asyncio
async def test_search_returns_results():
    reader = CogneeMemoryReader()
    results = await reader.search("test query", limit=5)
    assert isinstance(results, list)
    assert len(results) <= 5

@pytest.mark.asyncio
async def test_search_with_filters():
    reader = CogneeMemoryReader()
    results = await reader.search(
        "query",
        tags=["test"],
        min_importance=0.5
    )
    for result in results:
        assert "test" in result.tags
        assert result.importance >= 0.5
```

#### Integration Tests
```python
import pytest
from heretek_swarm.actors import ExplorerAgent
from heretek_swarm.memory import CogneeMemoryWriter

@pytest.mark.integration
@pytest.mark.asyncio
async def test_explorer_stores_observations():
    agent = ExplorerAgent(config)
    writer = CogneeMemoryWriter()

    # Agent observes
    observation = await agent.observe({"context": "test"})

    # Store in memory
    memory_id = await writer.add(
        content=observation,
        metadata={"agent": "explorer"}
    )

    assert memory_id is not None

#### Fixtures
```python
# conftest.py
import pytest
from heretek_swarm.memory import CogneeMemoryReader, CogneeMemoryWriter

@pytest.fixture
async def memory_reader():
    reader = CogneeMemoryReader()
    yield reader
    await reader.close()

@pytest.fixture
async def memory_writer():
    writer = CogneeMemoryWriter()
    yield writer
    await writer.close()

@pytest.fixture
def sample_memory():
    return {
        "content": "test memory content",
        "metadata": {
            "importance": 0.8,
            "tags": ["test", "sample"]
        }
    }
```

#### Mocking
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from heretek_swarm.memory import CogneeMemoryReader

@pytest.mark.asyncio
async def test_search_with_mock():
    # Mock the Cognee client
    mock_client = AsyncMock()
    mock_client.search.return_value = [
        {"id": "1", "content": "mocked result"}
    ]

    reader = CogneeMemoryReader(client=mock_client)
    results = await reader.search("query")

    assert len(results) == 1
    assert results[0]["content"] == "mocked result"
    mock_client.search.assert_called_once()
```

### Negative Assertions
```python
import pytest
from heretek_swarm.memory import __all__

def test_no_legacy_imports():
    """Verify legacy classes are not exported."""
    legacy_classes = [
        "DualTierMemory",
        "PersistentMemory",
        "TieringManager",
        "VersionedMemory",
        "CompressionManager"
    ]

    for legacy in legacy_classes:
        assert legacy not in __all__, f"Legacy class {legacy} should not be exported"

def test_no_legacy_modules():
    """Verify legacy modules are deleted."""
    import os
    memory_dir = "backend/heretek_swarm/memory"

    legacy_files = [
        "base.py",
        "persistent.py",
        "tiering.py",
        "versioned.py",
        "compression.py",
        "migration_strategies.py"
    ]

    for legacy in legacy_files:
        path = os.path.join(memory_dir, legacy)
        assert not os.path.exists(path), f"Legacy file {legacy} should be deleted"
```

## Frontend Testing

### Setup
```bash
cd swarm-dashboard
npm install
```

### Running Tests
```bash
# All tests
npm test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage

# Single file
npx vitest run src/__tests__/AgentCard.test.tsx
```

### Writing Tests

#### Unit Tests
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentCard } from '../components/AgentCard';

describe('AgentCard', () => {
  const mockAgent = {
    id: '1',
    name: 'Test Agent',
    status: 'active'
  };

  it('renders agent name', () => {
    render(<AgentCard agent={mockAgent} onSelect={() => {}} />);
    expect(screen.getByText('Test Agent')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', () => {
    const onSelect = vi.fn();
    render(<AgentCard agent={mockAgent} onSelect={onSelect} />);

    fireEvent.click(screen.getByText('Test Agent'));

    expect(onSelect).toHaveBeenCalledWith('1');
  });
});
```

#### Integration Tests
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../components/Dashboard';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

it('loads and displays agents', async () => {
  server.use(
    http.get('/api/agents', () => {
      return HttpResponse.json([
        { id: '1', name: 'Agent 1', status: 'active' }
      ]);
    })
  );

  render(<Dashboard />);

  await waitFor(() => {
    expect(screen.getByText('Agent 1')).toBeInTheDocument();
  });
});
```

#### Mocking API
```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/agents', () => {
    return HttpResponse.json([
      { id: '1', name: 'Agent 1', status: 'active' }
    ]);
  }),

  http.get('/api/agents/:id', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: `Agent ${params.id}`,
      status: 'active'
    });
  })
];
```

### Test Utilities
```typescript
// utils/test-utils.tsx
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    ),
    ...options,
  });
}
```

## Test Data Management

### Factories
```python
# tests/factories.py
import factory
from heretek_swarm.memory import MemoryAccessRecord

class MemoryFactory(factory.Factory):
    class Meta:
        model = MemoryAccessRecord

    content = factory.Faker('sentence')
    importance = factory.Faker('pyfloat', min_value=0, max_value=1)
    tags = factory.LazyFunction(lambda: ['test', 'sample'])
```

### Fixtures
```python
# tests/fixtures/memories.json
[
  {
    "id": "mem_001",
    "content": "Test memory 1",
    "importance": 0.8,
    "tags": ["test", "learning"]
  },
  {
    "id": "mem_002",
    "content": "Test memory 2",
    "importance": 0.6,
    "tags": ["observation"]
  }
]
```

## Test Categories

### Unit Tests
- Fast execution
- Isolated components
- Mock external dependencies
- High coverage target (80%+)

### Integration Tests
- Test component interactions
- Real database/service calls
- Slower execution
- Test critical paths

### End-to-End Tests
- Full user workflows
- Browser automation
- Slowest execution
- Critical user journeys

## CI/CD Integration

### GitHub Actions
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: uv sync
      - run: ruff check backend/ tests/
      - run: pytest tests/ -v --cov=heretek_swarm

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: cd swarm-dashboard && npm install
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

## Debugging Tests

### Common Issues

1. **Async tests not running**
   - Use `@pytest.mark.asyncio`
   - Check `asyncio_mode = "auto"` in config

2. **Flaky tests**
   - Add proper waits
   - Mock time-dependent code
   - Use deterministic test data

3. **Import errors**
   - Check test file location
   - Verify module paths
   - Use absolute imports

4. **Memory leaks**
   - Clean up fixtures
   - Close connections
   - Use context managers

### Debug Commands
```bash
# Verbose output
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -x

# Run last failed tests
pytest tests/ --lf

# Show local variables on failure
pytest tests/ --tb=long

# Debug with pdb
pytest tests/ --pdb
```

## Best Practices

1. **Test early, test often** - Write tests alongside code
2. **One assertion per test** - Keep tests focused
3. **Descriptive names** - Test names should explain intent
4. **Independent tests** - Tests shouldn't depend on each other
5. **Fast feedback** - Unit tests should run in milliseconds
6. **Clean tests** - Remove skipped/ignored tests regularly
7. **Test edge cases** - Include boundary conditions
8. **Mock external services** - Don't depend on external APIs
9. **Use fixtures** - Share test setup code
10. **Document complex tests** - Add comments for non-obvious assertions

## Coverage Requirements

- **New code**: 80%+ coverage required
- **Critical paths**: 90%+ coverage
- **Existing code**: Maintain current coverage
- **Coverage reports**: Generate in CI
- **Coverage gates**: Fail build if below threshold
