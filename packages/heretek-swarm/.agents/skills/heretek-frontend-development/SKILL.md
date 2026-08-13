---
name: heretek-frontend-development
description: >-
  Frontend development for Heretek Swarm React/TypeScript dashboard. Use when
  building UI components, implementing state management, or working with the
  Vite build system. Covers React 19 patterns, TypeScript conventions, and
  project-specific styling.
---

# Heretek Swarm Frontend Development

## Project Structure

```
swarm-dashboard/
├── src/
│   ├── components/      # React components
│   ├── hooks/           # Custom hooks
│   ├── services/        # API client services
│   ├── stores/          # State management
│   ├── types/           # TypeScript types
│   ├── utils/           # Utility functions
│   └── App.tsx          # Main application
├── public/              # Static assets
├── vite.config.ts       # Vite configuration
├── tsconfig.json        # TypeScript config
└── package.json         # Dependencies
```

## Tech Stack

- **React 19** with functional components
- **TypeScript** with strict mode
- **Vite 8** for build tooling
- **Vitest** for testing (NOT Jest)
- **ESLint** with strict rules
- **CSS Modules** or Tailwind CSS

## Conventions

### Code Style
- Functional components with hooks
- `useCallback` for memoized callbacks passed to children
- `const` assertions for literal types
- Explicit error handling on API calls
- Environment variables prefixed with `VITE_`

### TypeScript
- Strict mode enabled
- No `any` types - use proper typing
- Interface over type for object shapes
- Export types from dedicated `types/` directory

### Components
- One component per file
- Props interface defined above component
- Named exports preferred
- Avoid default exports

## Development Workflow

### Setup
```bash
cd swarm-dashboard
npm install
```

### Verification
```bash
# Lint (strict - zero warnings allowed)
npm run lint

# Type check + build
npm run build

# Tests
npm test

# Watch mode
npm run test:watch
```

### Build Output
```bash
# Production build
npm run build  # Creates dist/ directory

# Development server
npm run dev   # Starts at http://localhost:5173
```

## Common Patterns

### API Integration
```typescript
// services/api.ts
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export async function fetchAgents(): Promise<Agent[]> {
  const response = await fetch(`${API_BASE}/agents`);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}
```

### State Management
```typescript
// stores/agentStore.ts
import { create } from 'zustand';

interface AgentState {
  agents: Agent[];
  loading: boolean;
  error: string | null;
  fetchAgents: () => Promise<void>;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  loading: false,
  error: null,
  fetchAgents: async () => {
    set({ loading: true, error: null });
    try {
      const agents = await fetchAgents();
      set({ agents, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },
}));
```

### Component Pattern
```typescript
// components/AgentCard.tsx
import React, { useCallback } from 'react';
import { Agent } from '../types';

interface AgentCardProps {
  agent: Agent;
  onSelect: (id: string) => void;
}

export const AgentCard: React.FC<AgentCardProps> = ({ agent, onSelect }) => {
  const handleClick = useCallback(() => {
    onSelect(agent.id);
  }, [agent.id, onSelect]);

  return (
    <div className={styles.card} onClick={handleClick}>
      <h3>{agent.name}</h3>
      <p>{agent.status}</p>
    </div>
  );
};
```

## Testing Patterns

### Unit Tests
```typescript
// __tests__/AgentCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentCard } from '../components/AgentCard';

describe('AgentCard', () => {
  const mockAgent = {
    id: '1',
    name: 'Test Agent',
    status: 'active',
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

### Integration Tests
```typescript
// __tests__/Dashboard.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../components/Dashboard';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

it('loads and displays agents', async () => {
  server.use(
    http.get('/api/agents', () => {
      return HttpResponse.json([
        { id: '1', name: 'Agent 1', status: 'active' },
      ]);
    })
  );

  render(<Dashboard />);

  await waitFor(() => {
    expect(screen.getByText('Agent 1')).toBeInTheDocument();
  });
});
```

## Common Pitfalls

1. **Jest vs Vitest**: Project uses Vitest, not Jest. Don't use Jest APIs.
2. **Environment variables**: Must be prefixed with `VITE_` to be exposed to client.
3. **Strict linting**: ESLint configured with `--max-warnings 0` - zero tolerance.
4. **Build verification**: Always run `npm run build` to catch TypeScript errors.
5. **Mock service worker**: Use MSW for API mocking in tests.

## Performance Patterns

- Use `React.memo` for expensive components
- Implement `useMemo` for expensive calculations
- Use `useCallback` for functions passed as props
- Lazy load components with `React.lazy`
- Virtual scrolling for large lists

## Styling

- CSS Modules for component-scoped styles
- Tailwind CSS for utility classes
- Avoid inline styles
- Use CSS custom properties for theming
- Responsive design with mobile-first approach
