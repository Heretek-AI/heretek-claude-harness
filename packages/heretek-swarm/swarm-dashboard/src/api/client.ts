/**
 * API Client - Enhanced with error handling and retry logic
 *
 * Provides a centralized HTTP client with:
 * - Bearer token authentication
 * - Automatic retry for transient failures
 * - Error handling for 401/403/500 responses
 * - Request/response interceptors
 */

import axios, {
  AxiosError,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { useToast } from '../components/UI/Toast';

// Configuration
const API_URL = import.meta.env.VITE_API_HOST || localStorage.getItem('swarm_api_host') || '';
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms

// Toast instance holder (for use outside React components)
let toastInstance: { error: (title: string, message?: string) => void } | null = null;

export function setToastInstance(toast: { error: (title: string, message?: string) => void }) {
  toastInstance = toast;
}

// Error types
export enum ApiErrorCode {
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  SERVER_ERROR = 'SERVER_ERROR',
  NETWORK_ERROR = 'NETWORK_ERROR',
  TIMEOUT = 'TIMEOUT',
  UNKNOWN = 'UNKNOWN',
}

export class ApiError extends Error {
  code: ApiErrorCode;
  status?: number;
  data?: unknown;

  constructor(message: string, code: ApiErrorCode, status?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.data = data;
  }
}

// Create axios instance
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// Request interceptor - Add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const apiKey = localStorage.getItem('api_key');
    if (apiKey) {
      config.headers.Authorization = `Bearer ${apiKey}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor - Handle errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const data = error.response?.data as { message?: string } | undefined;
    const message = data?.message || error.message || 'An unexpected error occurred';

    let errorCode: ApiErrorCode;
    let errorMessage: string;

    switch (status) {
      case 401:
        errorCode = ApiErrorCode.UNAUTHORIZED;
        errorMessage = 'Authentication failed. Please check your API key.';
        // Optionally clear invalid token
        localStorage.removeItem('api_key');
        break;
      case 403:
        errorCode = ApiErrorCode.FORBIDDEN;
        errorMessage = 'Access denied. You do not have permission for this action.';
        break;
      case 404:
        errorCode = ApiErrorCode.NOT_FOUND;
        errorMessage = 'The requested resource was not found.';
        break;
      case 500:
      case 502:
      case 503:
      case 504:
        errorCode = ApiErrorCode.SERVER_ERROR;
        errorMessage = 'Server error. Please try again later.';
        break;
      default:
        if (error.code === 'ECONNABORTED') {
          errorCode = ApiErrorCode.TIMEOUT;
          errorMessage = 'Request timed out. Please try again.';
        } else if (error.code === 'ERR_NETWORK') {
          errorCode = ApiErrorCode.NETWORK_ERROR;
          errorMessage = 'Network error. Please check your connection.';
        } else {
          errorCode = ApiErrorCode.UNKNOWN;
          errorMessage = message;
        }
    }

    // Show toast notification for errors
    if (toastInstance) {
      toastInstance.error('API Error', errorMessage);
    } else {
      console.error('API Error:', errorMessage);
    }

    return Promise.reject(new ApiError(errorMessage, errorCode, status, data));
  },
);

// Retry logic wrapper
export async function withRetry<T>(
  fn: () => Promise<T>,
  retries = MAX_RETRIES,
  delay = RETRY_DELAY,
): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (retries <= 0) {
      throw error;
    }

    const apiError = error as ApiError;

    // Don't retry for client errors (4xx except 429)
    if (
      apiError instanceof ApiError &&
      apiError.status &&
      apiError.status >= 400 &&
      apiError.status < 500 &&
      apiError.status !== 429
    ) {
      throw error;
    }

    // Wait before retrying
    await new Promise((resolve) => setTimeout(resolve, delay));

    // Retry with exponential backoff
    return withRetry(fn, retries - 1, delay * 2);
  }
}

// Helper methods
export const api = {
  // GET request
  get: async <T>(url: string, config?: Omit<AxiosRequestConfig, 'data'>) => {
    return withRetry(() => apiClient.get<T>(url, config));
  },

  // POST request
  post: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig) => {
    return withRetry(() => apiClient.post<T>(url, data, config));
  },

  // PUT request
  put: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig) => {
    return withRetry(() => apiClient.put<T>(url, data, config));
  },

  // PATCH request
  patch: async <T>(url: string, data?: unknown, config?: AxiosRequestConfig) => {
    return withRetry(() => apiClient.patch<T>(url, data, config));
  },

  // DELETE request
  delete: async <T>(url: string, config?: Omit<AxiosRequestConfig, 'data'>) => {
    return withRetry(() => apiClient.delete<T>(url, config));
  },

  // Check if client is configured
  isConfigured: () => {
    return !!API_URL || typeof window !== 'undefined';
  },
};

// Export the axios instance for direct use if needed
export default apiClient;
