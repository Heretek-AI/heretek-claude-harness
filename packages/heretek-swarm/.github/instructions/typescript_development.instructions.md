---
applyTo: "**/*.tsx,**/*.ts"
---

# TypeScript/React Development Guidelines for Heretek Swarm

## Components
- Use functional components with hooks — no class components
- Prefer `useCallback` for memoized callbacks passed as props
- Use `useMemo` for expensive computations
- Keep components small — extract reusable logic into custom hooks

## API Calls
- Use `fetch` with proper error handling
- Always include `Authorization: Bearer` header when authenticated
- Handle loading, error, and empty states explicitly
- Use `AbortController` for cancellable requests

## State Management
- Use React context for global state (auth, theme, settings)
- Use local state for component-specific data
- Avoid prop drilling beyond 2 levels

## Styling
- Use CSS modules or Tailwind CSS
- Follow mobile-first responsive design
- Use CSS variables for theming

## Security
- Never store sensitive data in localStorage without encryption
- Sanitize user input before rendering
- Use `DOMPurify` for HTML content
- Never pass dynamic strings to `setTimeout`/`setInterval` — use function references
- Validate WebSocket message data before processing

## Testing
- Unit tests with Vitest for hooks and utilities
- Component tests with React Testing Library
- E2E tests with Playwright for critical flows
- Test loading, error, and empty states
