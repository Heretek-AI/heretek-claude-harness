"""
Logging Configuration for Heretek Swarm

Provides structured JSON logging with request tracing capabilities.
Configured for Loki + Promtail log aggregation.
"""

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import (
    CallsiteParameter,
    CallsiteParameterAdder,
    ExceptionRenderer,
    JSONRenderer,
    StackInfoRenderer,
    TimeStamper,
)
from structlog.stdlib import (
    ProcessorFormatter,
)
from structlog.types import Processor

# Context variables for request tracing
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
agent_id_var: ContextVar[str | None] = ContextVar("agent_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Log levels
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_var.get()


def get_agent_id() -> str | None:
    """Get the current agent ID from context."""
    return agent_id_var.get()


def get_trace_id() -> str | None:
    """Get the current trace ID from context."""
    return trace_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set the request ID in context. Generates one if not provided."""
    rid = request_id or str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


def set_agent_id(agent_id: str) -> None:
    """Set the agent ID in context."""
    agent_id_var.set(agent_id)


def set_trace_id(trace_id: str | None = None) -> str:
    """Set the trace ID in context. Generates one if not provided."""
    tid = trace_id or str(uuid.uuid4())
    trace_id_var.set(tid)
    return tid


def clear_context() -> None:
    """Clear all tracing context variables."""
    request_id_var.set(None)
    agent_id_var.set(None)
    trace_id_var.set(None)


class ContextAdder(Processor):
    """Processor that adds context variables to log entries."""

    def __call__(self, _logger, _method_name, event_dict):
        # Add request tracing context
        if request_id := get_request_id():
            event_dict["request_id"] = request_id
        if agent_id := get_agent_id():
            event_dict["agent_id"] = agent_id
        if trace_id := get_trace_id():
            event_dict["trace_id"] = trace_id
        return event_dict


def add_service_info(logger, method_name, event_dict):
    """Add service information to all log entries."""
    event_dict["service"] = "heretek-swarm"
    event_dict["environment"] = get_environment()
    return event_dict


def get_environment() -> str:
    """Get the current environment."""
    import os

    return os.getenv("ENVIRONMENT", "development")


def setup_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    include_caller_info: bool = True,
) -> None:
    """
    Configure structlog for structured JSON logging.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Output logs as JSON (required for Loki/Promtail)
        include_caller_info: Include caller filename and line number
    """
    # Determine processors based on output format
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso", utc=True),
        structlog.processors.UnicodeDecoder(),
        ContextAdder(),
        add_service_info,
    ]

    if include_caller_info:
        shared_processors.append(
            CallsiteParameterAdder(
                {
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                }
            )
        )

    # Add stack info and exception formatting for errors
    shared_processors.extend(
        [
            StackInfoRenderer(),
            ExceptionRenderer(),
        ]
    )

    # Configure renderer
    if json_output:
        # JSON output for Loki/Promtail ingestion
        renderer = JSONRenderer()
    else:
        # Human-readable console output for development
        renderer = ConsoleRenderer()

    # Chain processors with renderer
    processors = [*shared_processors, renderer]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level.upper())

    # Create formatter that structlog can process
    formatter = ProcessorFormatter(
        foreign_pre_chain=shared_processors[:-2],  # Exclude renderer and exception formatter
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically module path)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Default logger instance
logger = get_logger("heretek_swarm")


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str | None = None,
    agent_id: str | None = None,
    user_agent: str | None = None,
    client_ip: str | None = None,
) -> None:
    """
    Log an API request with standard fields for aggregation.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        request_id: Request tracing ID
        agent_id: Agent ID if applicable
        user_agent: Client user agent
        client_ip: Client IP address
    """
    log = logger.bind(
        event_type="api_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        request_id=request_id,
        agent_id=agent_id,
        user_agent=user_agent,
        client_ip=client_ip,
    )

    if status_code >= 500:
        log.error("API request failed")
    elif status_code >= 400:
        log.warning("API request client error")
    else:
        log.info("API request completed")


def log_agent_event(
    agent_id: str,
    event_type: str,
    message: str,
    level: str = "info",
    **extra: dict,
) -> None:
    """
    Log an agent event with standard fields.

    Args:
        agent_id: Agent identifier
        event_type: Type of event (e.g., 'start', 'stop', 'error', 'message')
        message: Event message
        level: Log level (debug, info, warning, error, critical)
        **extra: Additional fields to include
    """
    log = logger.bind(
        event_type="agent_event",
        agent_id=agent_id,
        event_subtype=event_type,
        message=message,
        **extra,
    )

    level = level.upper()
    if level == "DEBUG":
        log.debug(message)
    elif level == "INFO":
        log.info(message)
    elif level == "WARNING":
        log.warning(message)
    elif level == "ERROR":
        log.error(message)
    elif level == "CRITICAL":
        log.critical(message)
    else:
        log.info(message)
