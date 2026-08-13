"""Workflow execution event bus for SSE progress streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

_bus: WorkflowExecutionEventBus | None = None


class WorkflowExecutionEventBus:
    """In-process pub/sub for workflow execution progress events."""

    def __init__(self, max_history: int = 500) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history = max_history

    def subscribe(self, execution_id: str) -> asyncio.Queue[dict[str, Any]]:
        if execution_id not in self._queues:
            self._queues[execution_id] = asyncio.Queue(maxsize=256)
        return self._queues[execution_id]

    def emit(self, execution_id: str, event: dict[str, Any]) -> None:
        history = self._history[execution_id]
        history.append(event)
        if len(history) > self._max_history:
            del history[: len(history) - self._max_history]

        queue = self._queues.get(execution_id)
        if queue is not None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def get_history(self, execution_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(execution_id, []))

    def clear(self, execution_id: str) -> None:
        self._history.pop(execution_id, None)
        self._queues.pop(execution_id, None)


def get_execution_event_bus() -> WorkflowExecutionEventBus:
    global _bus
    if _bus is None:
        _bus = WorkflowExecutionEventBus()
    return _bus
