/**
 * Heretek Swarm - Docker Detection Hook
 *
 * Hook for detecting Docker availability and managing Docker-based services.
 */

import { useState, useEffect, useCallback } from 'react';

export interface DockerStatus {
  available: boolean;
  version: string | null;
  error: string | null;
  checking: boolean;
}

export interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'starting' | 'error' | 'unknown';
  health: 'healthy' | 'unhealthy' | 'unknown';
  ports?: Record<string, number>;
}

const DEFAULT_SERVICES: ServiceStatus[] = [
  { name: 'api', status: 'unknown', health: 'unknown', ports: { http: 8000 } },
  { name: 'frontend', status: 'unknown', health: 'unknown', ports: { http: 3000 } },
  { name: 'postgres', status: 'unknown', health: 'unknown', ports: { db: 5432 } },
  { name: 'redis', status: 'unknown', health: 'unknown', ports: { cache: 6379 } },
  { name: 'qdrant', status: 'unknown', health: 'unknown', ports: { http: 6333, grpc: 6334 } },
  { name: 'nats', status: 'unknown', health: 'unknown', ports: { http: 8222 } },
  { name: 'prometheus', status: 'unknown', health: 'unknown', ports: { http: 9090 } },
  { name: 'loki', status: 'unknown', health: 'unknown', ports: { http: 3100 } },
];

export function useDockerDetection() {
  const [dockerStatus, setDockerStatus] = useState<DockerStatus>({
    available: false,
    version: null,
    error: null,
    checking: true,
  });

  const [services, setServices] = useState<ServiceStatus[]>(DEFAULT_SERVICES);
  const [servicesLoading, setServicesLoading] = useState(false);

  // Check Docker status
  const checkDocker = useCallback(async () => {
    setDockerStatus(prev => ({ ...prev, checking: true }));

    try {
      // In Electron, this will call the main process
      if (typeof window !== 'undefined' && (window as any).heretek) {
        const status = await (window as any).heretek.checkDocker();
        setDockerStatus({
          available: status.available,
          version: status.version,
          error: status.error,
          checking: false,
        });
      } else {
        // Fallback for browser/dev mode
        // Try to fetch from API
        try {
          const response = await fetch('/health');
          if (response.ok) {
            setDockerStatus({
              available: true,
              version: 'API Connected',
              error: null,
              checking: false,
            });
          } else {
            setDockerStatus({
              available: false,
              version: null,
              error: 'API not reachable',
              checking: false,
            });
          }
        } catch {
          setDockerStatus({
            available: false,
            version: null,
            error: 'Docker services not running',
            checking: false,
          });
        }
      }
    } catch (error) {
      setDockerStatus({
        available: false,
        version: null,
        error: error instanceof Error ? error.message : 'Unknown error',
        checking: false,
      });
    }
  }, []);

  // Check services health
  const checkServices = useCallback(async () => {
    setServicesLoading(true);

    const healthEndpoints: Record<string, string> = {
      api: '/health',
      prometheus: '/-/healthy',
      loki: '/ready',
    };

    const updatedServices = await Promise.all(
      DEFAULT_SERVICES.map(async (service) => {
        const endpoint = healthEndpoints[service.name];
        if (!endpoint) {
          return { ...service, status: 'unknown', health: 'unknown' as const };
        }

        try {
          const response = await fetch(endpoint, {
            method: 'GET',
            signal: AbortSignal.timeout(5000),
          });

          if (response.ok) {
            return {
              ...service,
              status: 'running' as const,
              health: 'healthy' as const
            };
          } else {
            return {
              ...service,
              status: 'stopped' as const,
              health: 'unhealthy' as const
            };
          }
        } catch {
          return {
            ...service,
            status: 'stopped' as const,
            health: 'unknown' as const
          };
        }
      })
    );

    setServices(updatedServices as ServiceStatus[]);
    setServicesLoading(false);
  }, []);

  // Initial check
  useEffect(() => {
    checkDocker();
    checkServices();
  }, [checkDocker, checkServices]);

  // Periodic health checks
  useEffect(() => {
    const interval = setInterval(() => {
      if (dockerStatus.available) {
        checkServices();
      }
    }, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, [dockerStatus.available, checkServices]);

  // Start services (would trigger Docker compose up in main process)
  const startServices = useCallback(async () => {
    if (typeof window !== 'undefined' && (window as any).heretek) {
      // In Electron, this would trigger the main process
    } else {
      // Not available in browser mode
    }
  }, []);

  // Stop services
  const stopServices = useCallback(async () => {
    if (typeof window !== 'undefined' && (window as any).heretek) {
      // In Electron, this would trigger the main process
    } else {
      // Not available in browser mode
    }
  }, []);

  return {
    dockerStatus,
    services,
    servicesLoading,
    checkDocker,
    checkServices,
    startServices,
    stopServices,
  };
}

// Component for Docker status indicator
export function DockerStatusIndicator({
  status,
  size = 'md'
}: {
  status: DockerStatus;
  size?: 'sm' | 'md' | 'lg';
}) {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  const colorClasses = status.checking
    ? 'bg-yellow-500 animate-pulse'
    : status.available
    ? 'bg-green-500'
    : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <div className={`rounded-full ${sizeClasses[size]} ${colorClasses}`} />
      <span className="text-sm text-gray-400">
        {status.checking
          ? 'Checking...'
          : status.available
          ? `Docker ${status.version || 'Available'}`
          : 'Docker Not Available'}
      </span>
    </div>
  );
}

// Component for service status list
export function ServiceStatusList({
  services,
  onRefresh
}: {
  services: ServiceStatus[];
  onRefresh?: () => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-300">Services</h3>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="text-xs text-indigo-400 hover:text-indigo-300"
          >
            Refresh
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {services.map((service) => (
          <div
            key={service.name}
            className="flex items-center justify-between px-3 py-2 bg-gray-800 rounded-lg"
          >
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  service.status === 'running'
                    ? 'bg-green-500'
                    : service.status === 'starting'
                    ? 'bg-yellow-500 animate-pulse'
                    : service.status === 'error'
                    ? 'bg-red-500'
                    : 'bg-gray-500'
                }`}
              />
              <span className="text-sm text-gray-300 capitalize">{service.name}</span>
            </div>
            <span className="text-xs text-gray-500">
              {service.status === 'running' && service.ports
                ? Object.values(service.ports).join(':')
                : service.status === 'unknown'
                ? '-'
                : service.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Docker not available warning component
export function DockerWarning() {
  return (
    <div className="p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
      <div className="flex items-start gap-3">
        <div className="w-5 h-5 text-yellow-500 mt-0.5">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div>
          <h4 className="text-sm font-medium text-yellow-300">Docker Not Available</h4>
          <p className="mt-1 text-sm text-yellow-200/80">
            Docker is required to run Heretek Swarm services. Please install Docker Desktop
            and ensure it's running before starting services.
          </p>
          <a
            href="https://docs.docker.com/desktop/install/windows-install/"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center text-sm text-yellow-300 hover:text-yellow-200"
          >
            Install Docker Desktop
            <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}
