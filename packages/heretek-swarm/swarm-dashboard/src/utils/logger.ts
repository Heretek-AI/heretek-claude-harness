/**
 * Structured Logger for Heretek Swarm Frontend
 *
 * Provides leveled logging with timestamps, component context, and developer mode filtering.
 * Debug logs are only output when Developer Mode is enabled.
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  component: string;
  message: string;
  context?: Record<string, unknown>;
}

export interface Logger {
  debug: (message: string, context?: Record<string, unknown>) => void;
  info: (message: string, context?: Record<string, unknown>) => void;
  warn: (message: string, context?: Record<string, unknown>) => void;
  error: (message: string, context?: Record<string, unknown>) => void;
  log: (level: LogLevel, message: string, context?: Record<string, unknown>) => void;
}

class LoggerImpl implements Logger {
  private component: string;
  private isDeveloperMode: boolean;

  constructor(component: string = 'App') {
    this.component = component;
    this.isDeveloperMode = this.checkDeveloperMode();

    // Listen for developer mode changes
    if (typeof window !== 'undefined') {
      window.addEventListener('developer-mode-change', this.handleDeveloperModeChange as EventListener);
    }
  }

  private checkDeveloperMode(): boolean {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('developer_mode') === 'true';
  }

  private handleDeveloperModeChange = (event: CustomEvent) => {
    this.isDeveloperMode = event.detail.enabled;
  };

  private formatTimestamp(): string {
    return new Date().toISOString();
  }

  private createLogEntry(level: LogLevel, message: string, context?: Record<string, unknown>): LogEntry {
    return {
      timestamp: this.formatTimestamp(),
      level,
      component: this.component,
      message,
      context,
    };
  }

  private outputLog(entry: LogEntry) {
    // Always output errors and warnings
    if (entry.level === 'error' || entry.level === 'warn') {
      this.sendToConsole(entry);
      return;
    }

    // Only output debug/info when developer mode is enabled
    if (this.isDeveloperMode || entry.level === 'info') {
      this.sendToConsole(entry);
    }
  }

  private sendToConsole(entry: LogEntry) {
    const logPrefix = `[${entry.timestamp}] [${entry.level.toUpperCase()}] [${entry.component}]`;
    const logMessage = `${logPrefix} ${entry.message}`;

    switch (entry.level) {
      case 'debug':
        console.debug(logMessage, entry.context || '');
        break;
      case 'info':
        console.info(logMessage, entry.context || '');
        break;
      case 'warn':
        console.warn(logMessage, entry.context || '');
        break;
      case 'error':
        console.error(logMessage, entry.context || '');
        break;
    }

    // Also store in window for debug panel access
    if (typeof window !== 'undefined') {
      const logHistory = (window as unknown as { __logHistory?: LogEntry[] }).__logHistory || [];
      logHistory.push(entry);
      // Keep last 500 entries
      (window as unknown as { __logHistory: LogEntry[] }).__logHistory = logHistory.slice(-500);

      // Dispatch event for debug panel
      window.dispatchEvent(new CustomEvent('log-entry', { detail: entry }));
    }
  }

  log(level: LogLevel, message: string, context?: Record<string, unknown>) {
    const entry = this.createLogEntry(level, message, context);
    this.outputLog(entry);
  }

  debug(message: string, context?: Record<string, unknown>) {
    this.log('debug', message, context);
  }

  info(message: string, context?: Record<string, unknown>) {
    this.log('info', message, context);
  }

  warn(message: string, context?: Record<string, unknown>) {
    this.log('warn', message, context);
  }

  error(message: string, context?: Record<string, unknown>) {
    this.log('error', message, context);
  }

  destroy() {
    if (typeof window !== 'undefined') {
      window.removeEventListener('developer-mode-change', this.handleDeveloperModeChange as EventListener);
    }
  }
}

/**
 * Create a logger instance for a specific component
 */
export function createLogger(component: string = 'Unknown'): Logger {
  return new LoggerImpl(component);
}

/**
 * Get recent log history for debug panel
 */
export function getLogHistory(): LogEntry[] {
  if (typeof window === 'undefined') return [];
  return (window as unknown as { __logHistory?: LogEntry[] }).__logHistory || [];
}

/**
 * Clear log history
 */
export function clearLogHistory() {
  if (typeof window !== 'undefined') {
    (window as unknown as { __logHistory: LogEntry[] }).__logHistory = [];
  }
}

export default createLogger;
