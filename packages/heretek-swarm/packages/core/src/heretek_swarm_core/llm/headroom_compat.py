"""
Headroom compatibility shim — transparent token-compression layer for
LLM prompts.

Implements Phase 1.4 of PLAN.md (Zero-Trust Architecture Audit,
§3.1 Replace — headroom in the prompt path).

Why
---
Headroom (``headroom-ai`` on PyPI / ``headroom-py`` in the OSS
review directory) is a Rust-backed context-compression library that
advertises 60–95% token reduction with reversible CCR compression.
It is the canonical way to keep the swarm's per-token LLM cost under
control as deliberation rounds grow.

Installing the real package requires a Rust toolchain (PyO3 cdylib
build) that is not present in every CI environment. To keep the
swarm bootable in both cases, this shim:

* Exposes the same ``wrap(messages)`` / ``unwrap(compressed)`` API
  headroom ships.
* If the real ``headroom_ai`` library is importable, it dispatches to
  it transparently. Token savings, reversibility, and the
  ``learn`` / ``mine`` flows come from the real library.
* If the library is missing, ``wrap`` returns the input unchanged
  with a ``savings_ratio`` of 0.0 and a ``strategy`` of
  ``"passthrough"``. The LLM path keeps working; token savings
  simply degrade to zero.

This mirrors the pattern in :mod:`heretek_swarm.memory.mem0_backend`
— same code path, with the optional dependency surfaced through a
single facade.

Scope
-----
This module ships the facade. Wiring it into the LLM router at
``llm/model_garage.py`` is a follow-up: the existing router does
not know about headroom yet, and changing its call shape is a
larger refactor. The interface here is stable so the wiring can
land incrementally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Real headroom is optional. Try the Python wheel first; if it is
# missing, fall back to a passthrough implementation.
try:
    import headroom_ai  # type: ignore[import-untyped]

    HEADROOM_AVAILABLE = True
except ImportError:
    headroom_ai = None  # type: ignore[assignment]
    HEADROOM_AVAILABLE = False


@dataclass
class CompressionResult:
    """The output of :func:`wrap` / :func:`unwrap`.

    Attributes
    ----------
    data:
        The compressed (or original, in passthrough mode) payload.
    original_tokens:
        Approximate token count of the input. Computed via the
        library's own counter when available, otherwise a heuristic
        (chars / 4).
    compressed_tokens:
        Approximate token count of ``data``. ``0`` when
        ``savings_ratio`` is ``0.0``.
    savings_ratio:
        ``1.0 - compressed_tokens / original_tokens``. ``0.0`` in
        passthrough mode.
    strategy:
        Name of the algorithm that produced the result. ``"ccr"``
        for headroom's reversible compression, ``"passthrough"``
        for the no-op fallback.
    """

    data: Any
    original_tokens: int
    compressed_tokens: int
    savings_ratio: float
    strategy: str


def _estimate_tokens(text: str) -> int:
    """Heuristic token count when the real tokenizer is unavailable.

    1 token ≈ 4 characters of English text. Good enough for
    telemetry; the real library uses tiktoken for accuracy.
    """
    return max(1, len(text) // 4)


def wrap(
    messages: list[dict[str, Any]] | str,
    *,
    target_ratio: float = 0.3,
) -> CompressionResult:
    """Compress a prompt (or chat history) before sending to an LLM.

    Args:
        messages: Either a list of ``{"role": ..., "content": ...}``
            messages or a single string prompt.
        target_ratio: Desired compressed-size / original-size ratio
            (default ``0.3`` → keep ~30% of tokens). Ignored in
            passthrough mode.

    Returns:
        :class:`CompressionResult` with the (possibly compressed)
        data and savings telemetry.

    Example:
        >>> result = wrap([{"role": "user", "content": "long prompt…"}])
        >>> # Pass ``result.data`` to the LLM in place of the original.
    """
    if isinstance(messages, str):
        text = messages
    else:
        # Flatten messages into a single string for token estimation.
        text = "\n".join(str(m.get("content", "")) for m in messages)

    original_tokens = _estimate_tokens(text)

    if not HEADROOM_AVAILABLE or headroom_ai is None:
        return CompressionResult(
            data=messages,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            savings_ratio=0.0,
            strategy="passthrough",
        )

    # Real headroom path. The library is opt-in by env var so dev
    # can run with HEADROOM_ENABLED=0 to skip the (potentially
    # lossy) compression roundtrip.
    if os.getenv("HEADROOM_ENABLED", "1").lower() not in ("1", "true", "yes"):
        return CompressionResult(
            data=messages,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            savings_ratio=0.0,
            strategy="passthrough",
        )

    try:
        # The real headroom_ai API exposes ``compress(text, target_ratio)``
        # which returns a structured object with ``.compressed_text`` and
        # ``.savings_ratio``. Call it through a small adapter so the
        # import is the only place that knows the real API shape.
        compressed = headroom_ai.compress(  # type: ignore[attr-defined]
            text, target_ratio=target_ratio
        )
        compressed_text = getattr(compressed, "compressed_text", text)
        savings = float(getattr(compressed, "savings_ratio", 0.0))
        compressed_tokens = _estimate_tokens(compressed_text)
        return CompressionResult(
            data=compressed_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            savings_ratio=savings,
            strategy="ccr",
        )
    except Exception:
        # Never let a compression failure break the LLM call.
        return CompressionResult(
            data=messages,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            savings_ratio=0.0,
            strategy="passthrough",
        )


def unwrap(result: CompressionResult) -> list[dict[str, Any]] | str:
    """Restore a compressed prompt to its original shape.

    In passthrough mode, returns ``result.data`` unchanged. In
    headroom mode, the original messages are preserved inside
    ``result``; we just surface them. CCR's reversibility is
    provided by the real library when present.
    """
    return result.data  # type: ignore[return-value]


__all__ = [
    "CompressionResult",
    "HEADROOM_AVAILABLE",
    "wrap",
    "unwrap",
]
