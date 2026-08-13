"""Error handling utilities for API endpoints.

Provides helpers to sanitize error responses so that internal tracebacks
are never leaked to clients (CWE-209).
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

logger = logging.getLogger("api.errors")

# Generic message returned to clients when an internal error occurs.
# This prevents stack trace / implementation detail exposure.
INTERNAL_ERROR_MESSAGE = "An internal error occurred. The incident has been logged."


def sanitized_error(exc: Exception, *, context: str = "") -> dict[str, Any]:
    """Log the full traceback server-side and return a generic error payload.

    Args:
        exc: The caught exception.
        context: Optional human-readable label for the log entry
                 (e.g. endpoint name).

    Returns:
        A dict suitable for a JSON error response body.  Never includes
        the exception message or traceback.
    """
    tb = traceback.format_exc()
    logger.error(
        "api_internal_error",
        context=context,
        error_type=type(exc).__name__,
        error=str(exc),
        traceback=tb,
    )
    return {"status": "error", "message": INTERNAL_ERROR_MESSAGE}
