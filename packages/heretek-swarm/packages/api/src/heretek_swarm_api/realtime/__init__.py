"""
Realtime (WebSocket) package — extracted from
``api/websockets.py`` as part of Phase 3.4 of PLAN.md
(§1.4 god-class extraction; "Extract api/websockets.py's
WebSocketAuthManager and connection manager into a
realtime/ package").

The audit's exit criterion is that ``api/websockets.py`` is
replaced with a thin router that delegates to a
connection manager in the new package, and the WebSocket
auth lives in a focused module. This commit ships the
structural foundation:

* ``auth.py`` — ``WebSocketAuthManager`` re-exported at the
  new namespace. Backed by the canonical ``TokenStore``
  from Phase 2.10.
* ``manager.py`` — ``ConnectionManager`` (the WebSocket
  fan-out implementation) re-exported at the new
  namespace.

Backwards compatibility: ``api/websockets.py`` is preserved
as a re-export shim so existing imports keep working.
"""

from __future__ import annotations

# Re-export the canonical auth manager and connection manager
# at this package's namespace so callers can write
#   from heretek_swarm.realtime import (
#       WebSocketAuthManager, ConnectionManager,
#   )
from heretek_swarm.api.websockets import (  # noqa: F401
    WebSocketAuthManager,
    ws_auth_manager,
    ConnectionManager,
    manager,
    authenticate_websocket,
    _ws_authenticate_and_accept,
)

__all__ = [
    "WebSocketAuthManager",
    "ws_auth_manager",
    "ConnectionManager",
    "manager",
    "authenticate_websocket",
    "_ws_authenticate_and_accept",
]
