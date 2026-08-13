/**
 * Toast Notification System
 *
 * Provides toast notifications with support for different types,
 * auto-dismiss, and custom actions.
 */

import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => string;
  removeToast: (id: string) => void;
  success: (title: string, message?: string, duration?: number) => string;
  error: (title: string, message?: string, duration?: number) => string;
  warning: (title: string, message?: string, duration?: number) => string;
  info: (title: string, message?: string, duration?: number) => string;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

const typeConfig: Record<ToastType, { icon: string; bgColor: string; borderColor: string; textColor: string }> = {
  success: { icon: '✓', bgColor: 'bg-green-900/50', borderColor: 'border-green-500', textColor: 'text-green-400' },
  error: { icon: '✕', bgColor: 'bg-red-900/50', borderColor: 'border-red-500', textColor: 'text-red-400' },
  warning: { icon: '⚠', bgColor: 'bg-yellow-900/50', borderColor: 'border-yellow-500', textColor: 'text-yellow-400' },
  info: { icon: 'ℹ', bgColor: 'bg-blue-900/50', borderColor: 'border-blue-500', textColor: 'text-blue-400' },
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  const config = typeConfig[toast.type];
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleDismiss = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    onDismiss(toast.id);
  }, [toast.id, onDismiss]);

  React.useEffect(() => {
    if (toast.duration !== 0) {
      timeoutRef.current = setTimeout(handleDismiss, toast.duration || 5000);
    }
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [toast.duration, handleDismiss]);

  return (
    <div
      className={`${config.bgColor} ${config.borderColor} border-l-4 rounded-lg p-4 mb-3 min-w-[300px] max-w-md shadow-lg backdrop-blur-sm animate-slide-in-right`}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <span className={`${config.textColor} text-lg font-bold`}>{config.icon}</span>
        <div className="flex-1">
          <h4 className={`${config.textColor} font-semibold text-sm`}>{toast.title}</h4>
          {toast.message && (
            <p className="text-gray-300 text-sm mt-1">{toast.message}</p>
          )}
          {toast.action && (
            <button
              onClick={toast.action.onClick}
              className="mt-2 text-sm text-blue-400 hover:text-blue-300 underline"
            >
              {toast.action.label}
            </button>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className="text-gray-400 hover:text-white transition-colors"
          aria-label="Dismiss"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Generate unique ID using crypto for better randomness
  const addToast = useCallback((toast: Omit<Toast, 'id'>): string => {
    const array = new Uint8Array(9);
    crypto.getRandomValues(array);
    const id = Array.from(array, (b) => b.toString(36).padStart(2, '0')).join('').slice(0, 9);
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? 5000,
    };
    setToasts((prev) => [...prev, newToast]);
    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const success = useCallback((title: string, message?: string, duration?: number) => {
    return addToast({ type: 'success', title, message, duration });
  }, [addToast]);

  const error = useCallback((title: string, message?: string, duration?: number) => {
    return addToast({ type: 'error', title, message, duration });
  }, [addToast]);

  const warning = useCallback((title: string, message?: string, duration?: number) => {
    return addToast({ type: 'warning', title, message, duration });
  }, [addToast]);

  const info = useCallback((title: string, message?: string, duration?: number) => {
    return addToast({ type: 'info', title, message, duration });
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, warning, info }}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col items-end">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * ToastContainer - Alternative inline container (not using context)
 */
export interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
  className?: string;
}

export function ToastContainer({ toasts, onDismiss, className = '' }: ToastContainerProps) {
  return (
    <div className={`fixed top-4 right-4 z-50 flex flex-col items-end ${className}`}>
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export default ToastProvider;
