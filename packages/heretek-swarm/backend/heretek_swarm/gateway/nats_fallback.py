"""
In-memory fallback for the NATS event mesh.

Extracted from ``gateway/nats_event_mesh.py`` as part of Phase 2.1
of PLAN.md (§1.4 god-class extraction — nats_event_mesh.py was
1,888 LOC with 7+ concerns: connection, JetStream, consumers,
pub/sub, request/reply, mTLS, in-memory fallback, backoff).

The ``_InMemoryFallback`` class is the most self-contained
concern in the file: it implements the same pub/sub / request
/reply / wildcard subject matching surface as NATS, but in
process memory, so the swarm stays bootable when NATS is
unreachable. Extracting it lets:

* unit tests target the fallback in isolation
* other call sites (CLI tools, scripts, the cognee writer's
  prefetch path) reuse the in-memory mesh without pulling in
  the full NATS surface
* the audit's "split into connection / jetstream / subscriptions
  / tls / fallback" structure gets its first concrete sub-module

Backwards compatibility: ``from heretek_swarm.gateway.nats_event_mesh
import _InMemoryFallback`` keeps working — the parent module
re-exports the class from here.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any


class InMemoryFallback:
    """In-memory pub/sub + request/reply for when NATS is unavailable.

    Public class (no leading underscore) so it can be imported
    by other modules. The legacy name ``_InMemoryFallback`` in
    ``nats_event_mesh.py`` is a backwards-compat alias.

    Subject-pattern matching supports NATS wildcards:
    - ``>`` matches one or more tokens at the end (e.g. ``test.>``
      matches ``test.a.b.c``)
    - ``*`` matches exactly one token (e.g. ``events.*`` matches
      ``events.click`` but NOT ``events.click.button``)
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Callable]] = {}
        self._sub_counter = 0
        self._pending: dict[str, asyncio.Future] = {}

    @staticmethod
    def _matches_subject(pattern: str, subject: str) -> bool:
        if pattern == subject:
            return True

        pat_tokens = pattern.split(".")
        sub_tokens = subject.split(".")

        for i, pat_tok in enumerate(pat_tokens):
            if pat_tok == ">":
                # ``>`` must be the last token and consumes everything remaining
                return i == len(pat_tokens) - 1 and len(sub_tokens) > i
            if i >= len(sub_tokens):
                return False
            if pat_tok == "*":
                # Matches exactly one token — just continue
                continue
            if pat_tok != sub_tokens[i]:
                return False

        # All pattern tokens consumed — lengths must match exactly
        return len(pat_tokens) == len(sub_tokens)

    @property
    def subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return sum(len(subs) for subs in self._subscriptions.values())

    async def publish(self, subject: str, data: dict[str, Any]) -> bool:
        """Publish to in-memory subscribers."""
        for pattern, subs in self._subscriptions.items():
            if not self._matches_subject(pattern, subject):
                continue
            for sub in subs:
                with contextlib.suppress(Exception):
                    await sub(None, subject, data)
        return True

    async def send_to_json(
        self, subject: str, data_dict: dict[str, Any], **_kwargs: Any
    ) -> bool:
        """Send a message via in-memory fallback (delegates to publish)."""
        return await self.publish(subject, data_dict)

    async def broadcast_json(self, data_dict: dict[str, Any]) -> bool:
        """Broadcast via in-memory fallback (delegates to publish on "broadcast")."""
        return await self.publish("broadcast", data_dict)

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> str:
        """Subscribe in-memory."""
        sid = f"mem_{self._sub_counter}"
        self._sub_counter += 1

        if subject not in self._subscriptions:
            self._subscriptions[subject] = []
        self._subscriptions[subject].append(callback)

        return sid

    async def unsubscribe(self, _sid: str) -> bool:
        """Unsubscribe in-memory."""
        return True

    async def request(
        self,
        subject: str,
        data: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any] | None:
        """Request in-memory (no response by default)."""
        await self.publish(subject, data)
        return None


# Legacy alias for backwards compatibility.
_InMemoryFallback = InMemoryFallback


__all__ = ["InMemoryFallback", "_InMemoryFallback"]
