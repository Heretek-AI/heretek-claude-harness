---
name: heretek-contributing
description: >-
  Contribution guidelines for Heretek Swarm. Use when preparing contributions,
  creating pull requests, or following project conventions. Covers code style,
  commit messages, and review process.
---

# Contributing to Heretek Swarm

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 22 (see .nvmrc)
- Docker Desktop 4.x
- uv (Python package manager)

### Initial Setup
```bash
# Clone repository
git clone <repo-url>
cd heretek-swarm

# Install backend dependencies
uv sync

# Install frontend dependencies
cd swarm-dashboard
npm install

# Start development environment
docker compose up
```

## Code Style

### Python
- **Linting**: Ruff (target Python 3.11)
- **Type hints**: Required on all public APIs
- **Docstrings**: Google-style, max 120 chars
- **Imports**: Sorted by Ruff
- **Line length**: 120 characters max

```bash
# Check style
ruff check backend/ tests/

# Auto-fix
ruff check --fix backend/ tests/
```

### TypeScript
- **Linting**: ESLint with strict rules
- **TypeScript**: Strict mode enabled
- **Formatting**: Prettier
- **Warnings**: Zero warnings allowed

```bash
# Check style
cd swarm-dashboard
npm run lint

# Auto-fix
npm run lint -- --fix
```

## Commit Messages

### Conventional Commits
```
feat: add new agent type
fix: resolve memory leak in cache
docs: update API documentation
refactor: extract common utilities
test: add unit tests for auth module
chore: update dependencies
security: fix XSS vulnerability
```

### Commit Format
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Examples
```
feat(agents): add Explorer agent implementation

- Implement ExplorerAgent class
- Add observation capabilities
- Include memory integration

Closes #123
```

```
fix(memory): resolve cache invalidation issue

The cache was not being invalidated when memories were updated.
This caused stale data to be returned.

Fixes #456
```

## Pull Request Process

### Before Creating PR
1. **Run tests**: `pytest tests/ -v`
2. **Run linting**: `ruff check backend/ tests/`
3. **Run type check**: `mypy backend/heretek_swarm/`
4. **Update documentation** if needed
5. **Add tests** for new functionality

### PR Template
```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist

- [ ] Code follows project style
- [ ] Self-reviewed code
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests pass
```

### PR Title
Follow conventional commits format:
```
feat(agents): implement Explorer agent
```

## Code Review

### Review Checklist

#### Functionality
- [ ] Code does what it claims
- [ ] Edge cases handled
- [ ] Error handling appropriate
- [ ] Performance acceptable

#### Code Quality
- [ ] Follows project conventions
- [ ] No code duplication
- [ ] Clear variable/function names
- [ ] Proper documentation

#### Testing
- [ ] Tests cover new code
- [ ] Tests are meaningful
- [ ] Edge cases tested
- [ ] No flaky tests

#### Security
- [ ] Input validation
- [ ] No secrets in code
- [ ] Proper authentication
- [ ] Audit logging

### Review Etiquette
- Be constructive and respectful
- Focus on code, not person
- Provide suggestions, not just criticism
- Ask questions to understand
- Celebrate good work

## Testing Requirements

### Unit Tests
- **Coverage**: 80%+ for new code
- **Location**: `tests/` directory
- **Naming**: `test_<function>.py`
- **Frameworks**: pytest, pytest-asyncio

```python
@pytest.mark.asyncio
async def test_agent_creation():
    agent = Agent(name="test")
    assert agent.name == "test"
```

### Integration Tests
- **Coverage**: Critical paths
- **Location**: `tests/integration/`
- **Marking**: `@pytest.mark.integration`
- **Setup**: Use Docker Compose

```python
@pytest.mark.integration
async def test_agent_workflow():
    # Test full workflow
    pass
```

### Frontend Tests
- **Framework**: Vitest
- **Location**: `src/__tests__/` or `*.test.tsx`
- **Coverage**: 80%+ for new code

```typescript
it('renders agent name', () => {
    render(<AgentCard agent={mockAgent} />);
    expect(screen.getByText('Test Agent')).toBeInTheDocument();
});
```

## Documentation

### Code Documentation
```python
def complex_function(param1: str, param2: int) -> bool:
    """
    Brief description of function.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative

    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        True
    """
    pass
```

### API Documentation
- Use OpenAPI decorators
- Document all parameters
- Include examples
- Note breaking changes

### Architecture Documentation
- Update ARCHITECTURE.md for changes
- Document design decisions
- Include diagrams if helpful

## Branch Naming

### Format
```
<type>/<ticket-number>-<description>
```

### Examples
```
feature/123-explorer-agent
bugfix/456-memory-leak
hotfix/789-security-vulnerability
docs/101-api-documentation
```

## Development Workflow

### 1. Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/123-explorer-agent
```

### 2. Make Changes
```bash
# Make changes
# Write tests
# Update documentation
```

### 3. Verify Changes
```bash
# Run tests
pytest tests/ -v

# Run linting
ruff check backend/ tests/

# Run type check
mypy backend/heretek_swarm/
```

### 4. Commit Changes
```bash
git add .
git commit -m "feat(agents): implement Explorer agent"
```

### 5. Push and Create PR
```bash
git push origin feature/123-explorer-agent
# Create PR on GitHub
```

### 6. Address Review Feedback
```bash
# Make requested changes
# Push new commits
# Request re-review
```

### 7. Merge
```bash
# After approval
git checkout main
git pull origin main
git merge feature/123-explorer-agent
git push origin main
```

## Common Patterns

### Adding New Agent
1. Create directory under `actors/`
2. Implement `AgentActor` subclass
3. Add mixins as needed
4. Register in `actors/__init__.py`
5. Add configuration
6. Write tests
7. Update documentation

### Adding API Endpoint
1. Create router in `api/routers/`
2. Implement endpoints
3. Add Pydantic schemas
4. Register router
5. Add authentication
6. Write tests
7. Update OpenAPI docs

### Adding Memory Feature
1. Implement in `memory/` package
2. Add to `__init__.py` exports
3. Write unit tests
4. Write integration tests
5. Update documentation

## Code Quality Tools

### Ruff
```bash
# Check
ruff check backend/ tests/

# Fix
ruff check --fix backend/ tests/

# Format
ruff format backend/ tests/
```

### MyPy
```bash
# Type check
mypy backend/heretek_swarm/

# Check specific file
mypy backend/heretek_swarm/actors/base/core.py
```

### Pytest
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=heretek_swarm

# Run specific test
pytest tests/test_memory.py -v
```

## Getting Help

### Resources
- **Documentation**: `docs/` directory
- **Architecture**: `docs/ARCHITECTURE.md`
- **API Reference**: `docs/API_ENDPOINTS.md`
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

### Asking Questions
1. Check existing documentation first
2. Search GitHub Issues
3. Provide context and code samples
4. Be specific about the problem
5. Include error messages

## Recognition

### Contributors
- All contributors listed in CONTRIBUTORS.md
- Significant contributions highlighted in release notes
- Special recognition for major features

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Welcome newcomers
- Celebrate successes

## Release Process

### Versioning
Follow Semantic Versioning:
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes

### Release Checklist
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Version bumped
- [ ] Release notes written
- [ ] Tag created
- [ ] Published to PyPI/npm

## Gotchas

1. **Always run tests** before submitting
2. **Follow commit conventions**
3. **Update documentation** for changes
4. **Add tests** for new functionality
5. **Review your own code** first
6. **Keep PRs focused** - one feature per PR
7. **Respond to feedback** promptly
8. **Be patient** - reviews take time

## Best Practices

1. Write clean, readable code
2. Follow project conventions
3. Test thoroughly
4. Document changes
5. Communicate clearly
6. Be respectful
7. Help others
8. Learn continuously
