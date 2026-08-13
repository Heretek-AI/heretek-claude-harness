# Developer Mode & Debug Features

This document describes the debuggability features implemented in the Heretek Swarm Dashboard frontend.

## Overview

The frontend now includes comprehensive developer tools for debugging, monitoring, and troubleshooting. These features are accessible through the **Developer Mode** toggle in the Settings page.

## Enabling Developer Mode

1. Navigate to **Settings** (⚙️) in the sidebar
2. Find the **Developer Tools** section at the top
3. Toggle the **Developer Mode** switch to enable

Once enabled, the following debug features become available:

## Debug Features

### 1. Debug Panel (Ctrl+Shift+D)

A collapsible, dockable panel in the bottom-right corner providing:

- **Logs Tab**: Real-time structured log viewer with level filtering (Debug, Info, Warn, Error)
- **API Tab**: API request history showing method, URL, status code, and response times
- **State Tab**: Zustand state transition history with before/after state comparison
- **Network Tab**: Network request waterfall with status indicators

**Keyboard Shortcut**: Press `Ctrl+Shift+D` (or `Cmd+Shift+D` on Mac) to toggle the panel.

### 2. Performance Overlay

Real-time performance monitoring displayed in the top-right corner:

- **FPS Counter**: Live frames-per-second with color coding (green ≥55, yellow ≥30, red <30)
- **Frame Time**: Current render time in milliseconds
- **Memory Usage**: JavaScript heap memory consumption (when available)
- **Network Stats**: Request count and total time
- **Component Renders**: Total render count

Click the expand button (▼) for detailed metrics view.

### 3. Structured Logging

The `logger.ts` utility provides leveled logging with context:

```typescript
import createLogger from './utils/logger';

const logger = createLogger('MyComponent');

logger.debug('Debug message', { data: someData });
logger.info('Info message');
logger.warn('Warning message', { context: 'important' });
logger.error('Error message', { error: someError });
```

**Log Levels**:
- `debug`: Only shown when Developer Mode is enabled
- `info`: Always shown
- `warn`: Always shown
- `error`: Always shown

Logs are stored in `window.__logHistory` for debug panel access.

### 4. Component Error Boundaries

Per-component error handling that prevents entire dashboard crashes:

```typescript
import { ComponentErrorBoundary, withErrorBoundary } from './components/UI';

// Class-based usage
<ComponentErrorBoundary componentName="AgentList" retryable>
  <AgentList />
</ComponentErrorBoundary>

// HOC usage
const ProtectedAgentList = withErrorBoundary(AgentList, {
  componentName: 'AgentList',
  logToBackend: true,
});
```

**Features**:
- Graceful fallback UI
- Retry mechanism (up to 3 attempts)
- Error logging to console and optionally backend
- Expandable error details

### 5. Zustand Store Debug Middleware

State transitions are automatically logged when Developer Mode is enabled:

```typescript
import { create } from 'zustand';
import { withDebugMiddleware } from './store/middleware/debugMiddleware';

export const useStore = create(
  withDebugMiddleware((set, get) => ({
    // Your state and actions
  }), {
    logToConsole: true,
    logToWindow: true,
    skipActions: [], // Actions to skip logging
  })
);
```

**Logged Information**:
- Action type
- Previous state
- Next state
- Changed values (diff)

## File Structure

```
dashboard/frontend/src/
├── components/
│   ├── Settings/
│   │   └── DeveloperModeToggle.tsx    # Toggle component + useDeveloperMode hook
│   └── UI/
│       ├── DebugPanel.tsx              # Main debug panel
│       ├── PerformanceOverlay.tsx      # Performance monitoring
│       └── ComponentErrorBoundary.tsx  # Error boundary wrapper
├── store/
│   └── middleware/
│       └── debugMiddleware.ts          # Zustand debug middleware
└── utils/
    └── logger.ts                       # Structured logging utility
```

## Dependencies Added

```json
{
  "dependencies": {
    "pino": "^8.21.0",
    "pino-pretty": "^10.3.1"
  }
}
```

Note: The logger implementation uses a custom solution for browser compatibility, but pino is available for future enhancements or server-side logging.

## Configuration Files

- `tailwind.config.js`: Tailwind CSS configuration with custom colors
- `postcss.config.js`: PostCSS configuration for Tailwind integration

## API Integration

The debug panel listens for custom events:

- `log-entry`: New log entries
- `api-request`: API request/response data
- `state-transition`: Zustand state changes
- `network-request`: Network activity
- `component-render`: Component render tracking

Dispatch these events to integrate your own components with the debug panel:

```typescript
window.dispatchEvent(new CustomEvent('api-request', {
  detail: {
    id: 'unique-id',
    method: 'GET',
    url: '/api/v1/agents',
    startTime: Date.now(),
    endTime: Date.now() + 100,
    duration: 100,
    status: 200,
  }
}));
```

## Performance Considerations

- Debug features have minimal impact when Developer Mode is disabled
- Performance overlay uses `requestAnimationFrame` for accurate FPS measurement
- Log history is limited to 500 entries to prevent memory issues
- State transition history is limited to 100 entries

## Best Practices

1. **Always wrap components** with `ComponentErrorBoundary` in production
2. **Use structured logging** instead of `console.log` for consistency
3. **Clear debug data** periodically using the panel's clear buttons
4. **Monitor FPS** during development to catch performance issues early
5. **Review state transitions** when debugging complex interactions
