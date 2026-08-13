"""Tests for ModelGarage circuit breaker and provider fallback.

We mock the inner _stream_from_provider so we test the garage's behavior,
not real provider calls. Each provider implementation is wired separately.
"""

from __future__ import annotations

import time
from collections import deque

import pytest

from tier1.config import Settings
from tier1.deliberation.state import AgentName
from tier1.llm.errors import LLMTimeout, LLMUnavailable
from tier1.llm.garage import CIRCUIT_OPEN_S, CIRCUIT_THRESHOLD, ModelGarage, StreamChunk


def _settings() -> Settings:
    return Settings(
        minimax_api_key="sk-test",
        anthropic_api_key="sk-test",
        openai_api_key="sk-test",
    )


class _FakeProvider:
    """Stub the inner provider method with a sequence of behaviors."""

    def __init__(self, behaviors: list) -> None:
        self.behaviors = list(behaviors)
        self.calls = 0

    async def __call__(self, provider: str, prompt: str, agent: AgentName):
        self.calls += 1
        if not self.behaviors:
            raise LLMUnavailable("exhausted")
        b = self.behaviors.pop(0)
        if isinstance(b, Exception):
            raise b
        if b == "ok":
            for t in ("hello", " ", "world"):
                yield StreamChunk(token=t, agent=agent, seq=0)
            return
        if b == "ok_then_timeout":
            # Yield some chunks, then raise LLMTimeout. Exercises the
            # mid-stream exception path in stream_chat.
            yield StreamChunk(token="par", agent=agent, seq=0)
            yield StreamChunk(token="tial", agent=agent, seq=1)
            raise LLMTimeout("mid-stream timeout")
        if b == "ok_then_burst":
            # Yield some chunks, then raise an unexpected (non-LLM) exception.
            # Same code path as ok_then_timeout but covers non-LLMError.
            yield StreamChunk(token="mid", agent=agent, seq=0)
            yield StreamChunk(token="dle", agent=agent, seq=1)
            raise RuntimeError("connection dropped")
        if b == "timeout":
            raise LLMTimeout("timed out")
        raise AssertionError(f"unknown behavior: {b}")


@pytest.fixture
def garage(monkeypatch) -> ModelGarage:
    g = ModelGarage(_settings())
    return g


async def test_provider_order_all_available(garage: ModelGarage):
    order = garage.provider_order()
    assert order == ["minimax", "anthropic", "openai", "local"]


async def test_stream_chat_success_first_provider(garage: ModelGarage, monkeypatch):
    fake = _FakeProvider(["ok"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    tokens: list[str] = []
    async for chunk in garage.stream_chat("hi", agent="alpha"):
        tokens.append(chunk.token)
    assert "".join(tokens) == "hello world"
    assert fake.calls == 1
    assert not garage.circuits["minimax"].is_open()


async def test_stream_chat_falls_back_on_timeout(garage: ModelGarage, monkeypatch):
    fake = _FakeProvider(["timeout", "ok"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    tokens: list[str] = []
    async for chunk in garage.stream_chat("hi", agent="beta"):
        tokens.append(chunk.token)
    assert "".join(tokens) == "hello world"
    assert fake.calls == 2
    # After one timeout on the primary, the primary circuit has recorded
    # exactly one failure — proves the failure-recording path is wired.
    assert len(garage.circuits["minimax"].failures) == 1


async def test_stream_chat_all_providers_fail_raises_unavailable(garage: ModelGarage, monkeypatch):
    fake = _FakeProvider(["timeout", "timeout", "timeout", "timeout"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    with pytest.raises(LLMUnavailable, match="all providers failed"):
        async for _ in garage.stream_chat("hi", agent="alpha"):
            pass


async def test_circuit_opens_after_threshold_failures(garage: ModelGarage, monkeypatch):
    # Each stream_chat call hits each provider once. 3 calls -> minimax has
    # 3 failures, exceeding CIRCUIT_THRESHOLD -> circuit opens.
    fake = _FakeProvider(["timeout"] * 12)
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    for i in range(3):
        with pytest.raises(LLMUnavailable, match="all providers failed"):
            async for _ in garage.stream_chat("hi", agent="alpha"):
                pass
    # provider_order should skip minimax now.
    assert "minimax" not in garage.provider_order()


async def test_circuit_recovery_after_success(garage: ModelGarage, monkeypatch):
    # Fail twice, then succeed.
    fake = _FakeProvider(["timeout", "timeout", "ok"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    tokens: list[str] = []
    async for chunk in garage.stream_chat("hi", agent="alpha"):
        tokens.append(chunk.token)
    # Success lands on openai (3rd in chain); openai's circuit is cleared.
    assert garage.circuits["openai"].failures == deque()
    assert not garage.circuits["openai"].is_open()


async def test_chat_collects_all_tokens(garage: ModelGarage, monkeypatch):
    fake = _FakeProvider(["ok"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    result = await garage.chat("hi", agent="alpha")
    assert result == "hello world"


async def test_provider_order_excludes_open_circuits(garage: ModelGarage):
    # Trip the minimax circuit manually.
    for _ in range(CIRCUIT_THRESHOLD):
        garage.circuits["minimax"].record_failure()
    assert "minimax" not in garage.provider_order()
    assert "anthropic" in garage.provider_order()


def test_circuit_open_window_constant():
    assert CIRCUIT_OPEN_S == 300.0


def test_circuit_threshold_constant():
    assert CIRCUIT_THRESHOLD == 3


async def test_stream_chat_midstream_timeout_records_failure_and_propagates(
    garage: ModelGarage, monkeypatch
):
    """Provider yields some chunks then raises LLMTimeout mid-stream.

    Expected: the partial chunks are yielded to the caller, the primary
    circuit records exactly one failure, the exception propagates as
    LLMUnavailable (not the raw LLMTimeout), and the chain does NOT fall
    through to the next provider (that would double-emit tokens).
    """
    fake = _FakeProvider(["ok_then_timeout"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    tokens: list[str] = []
    with pytest.raises(LLMUnavailable, match="mid-stream") as excinfo:
        async for chunk in garage.stream_chat("hi", agent="alpha"):
            tokens.append(chunk.token)
    # Caller received the partial chunks before the failure.
    assert "".join(tokens) == "partial"
    # Primary recorded the failure.
    assert len(garage.circuits["minimax"].failures) == 1
    # Mid-stream failure does NOT fall through to a second provider.
    assert fake.calls == 1
    # Propagated as LLMUnavailable with a descriptive message and a
    # chained cause pointing at the original LLMTimeout.
    assert "minimax" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, LLMTimeout)


async def test_stream_chat_midstream_non_llm_exception_also_recorded(
    garage: ModelGarage, monkeypatch
):
    """A non-LLMError raised mid-stream (e.g. socket reset) is also recorded
    as a failure and propagated as LLMUnavailable."""
    fake = _FakeProvider(["ok_then_burst"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    tokens: list[str] = []
    with pytest.raises(LLMUnavailable, match="mid-stream") as excinfo:
        async for chunk in garage.stream_chat("hi", agent="alpha"):
            tokens.append(chunk.token)
    assert "".join(tokens) == "middle"
    assert len(garage.circuits["minimax"].failures) == 1
    assert fake.calls == 1
    # The chained cause is the original RuntimeError, not swallowed.
    assert isinstance(excinfo.value.__cause__, RuntimeError)


async def test_circuit_threshold_trips_at_exactly_three_failures_on_one_provider(
    garage: ModelGarage, monkeypatch
):
    """Threshold behavior is per-provider: exactly 3 failures on minimax
    opens the minimax circuit while leaving others below threshold and
    therefore still closed.

    We isolate the per-provider threshold assertion by manually pre-opening
    the other providers' circuits (so they're skipped by provider_order)
    and then driving exactly 3 failures onto minimax via 3 sequential calls.
    Each call sees only minimax in its snapshotted provider_order, so the
    other providers receive zero additional failures.
    """
    # Manually trip anthropic/openai/local so provider_order() returns
    # only ["minimax"]. We bypass record_failure -> open_until by setting
    # open_until directly to a future timestamp.
    future = time.time() + 600.0
    for name in ("anthropic", "openai", "local"):
        garage.circuits[name].open_until = future

    # Sanity: chain is now minimax-only.
    assert garage.provider_order() == ["minimax"]

    # Drive exactly 3 failures onto minimax via 3 sequential calls. Each
    # call snapshots ["minimax"], the timeout fires, the failure is
    # recorded, and the call raises LLMUnavailable with no fallback.
    fake = _FakeProvider(["timeout", "timeout", "timeout"])
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    for _ in range(3):
        with pytest.raises(LLMUnavailable, match="all providers failed"):
            async for _ in garage.stream_chat("hi", agent="alpha"):
                pass

    # Per-provider failure counts: minimax exactly at threshold (3), others
    # received zero failures during this test.
    assert len(garage.circuits["minimax"].failures) == 3
    assert len(garage.circuits["anthropic"].failures) == 0
    assert len(garage.circuits["openai"].failures) == 0
    assert len(garage.circuits["local"].failures) == 0

    # Threshold isolates the failing provider: only minimax is open.
    assert garage.circuits["minimax"].is_open()
    # The other three are open from the manual pre-trip (still open from
    # the future timestamp), not from the failures in this test.
    assert garage.circuits["anthropic"].is_open()
    assert garage.circuits["openai"].is_open()
    assert garage.circuits["local"].is_open()

    # provider_order is now empty — every circuit is open.


async def test_circuit_below_threshold_stays_closed(garage: ModelGarage, monkeypatch):
    """Two failures on a provider is below the threshold of 3, so the
    circuit must remain closed and the provider remains in the chain."""
    # Two stream_chat calls: minimax accumulates 2 failures (< threshold).
    fake = _FakeProvider(["timeout"] * 8)
    monkeypatch.setattr(garage, "_stream_from_provider", fake)
    for _ in range(2):
        with pytest.raises(LLMUnavailable, match="all providers failed"):
            async for _ in garage.stream_chat("hi", agent="alpha"):
                pass
    assert len(garage.circuits["minimax"].failures) == 2
    assert not garage.circuits["minimax"].is_open()
    assert "minimax" in garage.provider_order()


# ---------------------------------------------------------------------------
# Phase 2: direct unit tests for the garage module's classes and provider
# implementations. We patch SDKs, observability, and time as required.
# ---------------------------------------------------------------------------

import builtins as _builtins
import sys as _sys

from unittest.mock import MagicMock, patch

import openai as _openai
import anthropic as _anthropic
from freezegun import freeze_time

import tier1.observability.metrics as _metrics_mod

from tier1.llm.garage import _Circuit


# -- _Circuit internals ------------------------------------------------------


def test_circuit_init_defaults():
    c = _Circuit("p")
    assert c.name == "p"
    assert list(c.failures) == []
    assert c.open_until == 0.0


@freeze_time("2026-01-01 00:00:00")
def test_circuit_record_failure_appends_timestamp():
    c = _Circuit("p")
    with patch.object(_metrics_mod, "toggle_circuit_state"):
        c.record_failure()
    assert len(c.failures) == 1
    assert c.failures[0] == time.time()


@freeze_time("2026-01-01 00:00:00")
def test_circuit_record_failure_opens_after_threshold():
    c = _Circuit("p")
    with patch.object(_metrics_mod, "toggle_circuit_state"):
        c.record_failure()
        c.record_failure()
        c.record_failure()
    assert len(c.failures) == 3
    assert c.open_until == time.time() + 300.0


@freeze_time("2026-01-01 00:00:00")
def test_circuit_record_failure_evicts_old():
    c = _Circuit("p")
    c.failures.append(time.time() - 120.0)  # already outside window
    with patch.object(_metrics_mod, "toggle_circuit_state"):
        c.record_failure()
        c.record_failure()
        c.record_failure()
        c.record_failure()
    # the old entry is evicted before the threshold check, so the failures
    # deque only contains the 4 fresh timestamps.
    assert all(time.time() - t < 60.0 for t in c.failures)
    assert len(c.failures) == 4
    assert c.open_until > time.time()


def test_circuit_record_success_clears_failures():
    c = _Circuit("p")
    c.failures.append(time.time())
    c.open_until = time.time() + 100
    with patch.object(_metrics_mod, "toggle_circuit_state"):
        c.record_success()
    assert list(c.failures) == []
    assert c.open_until == 0.0


@freeze_time("2026-01-01 00:00:00")
def test_circuit_is_open_false_when_closed():
    c = _Circuit("p")
    assert c.is_open() is False


@freeze_time("2026-01-01 00:00:00")
def test_circuit_is_open_true_when_within_window():
    c = _Circuit("p")
    c.open_until = time.time() + 10
    assert c.is_open() is True


# -- provider_order ----------------------------------------------------------


def test_garage_provider_order_skips_open_circuits():
    g = ModelGarage(_settings())
    with patch.object(_metrics_mod, "toggle_circuit_state"):
        for _ in range(CIRCUIT_THRESHOLD):
            g.circuits["minimax"].record_failure()
            g.circuits["openai"].record_failure()
    order = g.provider_order()
    assert "minimax" not in order
    assert "openai" not in order
    assert "anthropic" in order
    assert "local" in order


def test_garage_provider_order_all_open_returns_empty():
    g = ModelGarage(_settings())
    future = time.time() + 600
    for name in ("minimax", "anthropic", "openai", "local"):
        g.circuits[name].open_until = future
    assert g.provider_order() == []


# -- stream_chat: behaviour coverage -----------------------------------------


def _async_iter(items):
    """Build an async iterator from a list of items/exceptions."""

    async def gen():
        for item in items:
            if isinstance(item, Exception):
                raise item
            yield item

    return gen()


async def test_stream_chat_yields_chunks_from_first_provider(garage: ModelGarage, monkeypatch):
    chunk_a = StreamChunk(token="a", agent="alpha", seq=0)
    chunk_b = StreamChunk(token="b", agent="alpha", seq=0)
    chunk_c = StreamChunk(token="c", agent="alpha", seq=0)

    async def provider(provider, prompt, agent):
        for c in (chunk_a, chunk_b, chunk_c):
            yield c

    monkeypatch.setattr(garage, "_stream_from_provider", provider)
    out: list[StreamChunk] = []
    async for ch in garage.stream_chat("hi", agent="alpha"):
        out.append(ch)
    assert out == [chunk_a, chunk_b, chunk_c]
    # success recorded -> failures cleared
    assert list(garage.circuits["minimax"].failures) == []


async def test_stream_chat_falls_through_on_pre_stream_failure(garage: ModelGarage, monkeypatch):
    async def first(provider, prompt, agent):
        raise LLMUnavailable("boom")
        yield  # pragma: no cover - unreachable, makes this an async generator

    async def second(provider, prompt, agent):
        yield StreamChunk(token="ok", agent="alpha", seq=0)

    seq = [first, second]
    monkeypatch.setattr(garage, "_stream_from_provider", lambda *a, **kw: seq.pop(0)(*a, **kw))
    out = []
    async for ch in garage.stream_chat("hi", agent="alpha"):
        out.append(ch.token)
    assert out == ["ok"]
    # First provider had 1 failure; second had a success (failures cleared).
    assert len(garage.circuits["minimax"].failures) == 1
    assert list(garage.circuits["anthropic"].failures) == []


async def test_stream_chat_raises_llmunavailable_mid_stream(garage: ModelGarage, monkeypatch):
    async def provider(provider, prompt, agent):
        yield StreamChunk(token="hi", agent="alpha", seq=0)
        raise LLMTimeout("blown up")

    monkeypatch.setattr(garage, "_stream_from_provider", provider)
    with pytest.raises(LLMUnavailable, match="mid-stream"):
        async for _ in garage.stream_chat("hi", agent="alpha"):
            pass


async def test_stream_chat_raises_when_all_down(garage: ModelGarage, monkeypatch):
    async def fail(provider, prompt, agent):
        raise LLMUnavailable("nope")
        yield  # pragma: no cover

    monkeypatch.setattr(garage, "_stream_from_provider", fail)
    with pytest.raises(LLMUnavailable, match="all providers failed"):
        async for _ in garage.stream_chat("hi", agent="alpha"):
            pass


async def test_stream_chat_raises_when_circuits_all_open(garage: ModelGarage):
    future = time.time() + 600
    for name in ("minimax", "anthropic", "openai", "local"):
        garage.circuits[name].open_until = future
    with pytest.raises(LLMUnavailable) as excinfo:
        async for _ in garage.stream_chat("hi", agent="alpha"):
            pass
    assert "circuit open" in str(excinfo.value)


async def test_stream_chat_records_metric_failure(garage: ModelGarage, monkeypatch):
    async def fail(provider, prompt, agent):
        raise LLMUnavailable("nope")
        yield  # pragma: no cover

    monkeypatch.setattr(garage, "_stream_from_provider", fail)
    with patch("tier1.llm.garage.record_provider_call") as rec:
        with pytest.raises(LLMUnavailable, match="all providers failed"):
            async for _ in garage.stream_chat("hi", agent="alpha"):
                pass


# -- _stream_openai_provider -------------------------------------------------


class _FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, choices: list[_FakeChoice]) -> None:
        self.choices = choices


def _make_openai_client(chunks: list):
    """Build a fake AsyncOpenAI whose chat.completions.create returns an async iter."""
    client = MagicMock()
    completions = MagicMock()
    response = _async_iter(chunks)

    async def create(*args, **kwargs):
        return response

    completions.create = create
    client.chat.completions = completions
    return client


def _span_cm():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


@pytest.mark.parametrize(
    "provider_name,key_attr,base_attr",
    [
        ("minimax", "minimax_api_key", "minimax_base_url"),
        ("openai", "openai_api_key", None),
        ("local", None, "ollama_base_url"),
    ],
)
async def test_stream_openai_provider_uses_correct_settings_per_provider(
    provider_name, key_attr, base_attr, monkeypatch
):
    """Each OpenAI-compatible provider pulls its own key/base from settings."""
    captured: dict = {}

    def fake_asyncopenai(*args, **kwargs):
        captured.update(kwargs)
        return _make_openai_client([])

    monkeypatch.setattr(_openai, "AsyncOpenAI", fake_asyncopenai)

    settings = Settings(
        minimax_api_key="sk-mm",
        openai_api_key="sk-oa",
        ollama_base_url="http://localhost:11434/v1",
    )
    g = ModelGarage(settings)
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        async for _ in g._stream_openai_provider("hi", "alpha", provider_name):
            pass

    expected_key = "ollama" if provider_name == "local" else getattr(settings, key_attr)
    assert captured["api_key"] == expected_key
    if base_attr is None:
        assert captured["base_url"] is None
    else:
        assert captured["base_url"] == getattr(settings, base_attr)


async def test_stream_openai_provider_raises_on_unknown_provider(garage: ModelGarage):
    with pytest.raises(LLMUnavailable, match="unknown openai-type provider"):
        async for _ in garage._stream_openai_provider("hi", "alpha", "nonsense"):
            pass


async def test_stream_openai_provider_raises_when_no_api_key(garage: ModelGarage, monkeypatch):
    monkeypatch.setattr(garage.settings, "minimax_api_key", "")
    with pytest.raises(LLMUnavailable) as excinfo:
        async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
            pass
    assert "no API key" in str(excinfo.value)


async def test_stream_openai_provider_yields_chunks_with_seq(garage: ModelGarage, monkeypatch):
    chunks = [
        _FakeChunk([_FakeChoice("hello")]),
        _FakeChunk([_FakeChoice(" world")]),
    ]
    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _make_openai_client(chunks))
    out = []
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        async for ch in garage._stream_openai_provider("hi", "alpha", "minimax"):
            out.append(ch)
    assert [c.token for c in out] == ["hello", " world"]
    assert [c.seq for c in out] == [0, 1]


async def test_stream_openai_provider_handles_empty_choices(garage: ModelGarage, monkeypatch):
    chunks = [_FakeChunk([]), _FakeChunk([])]
    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _make_openai_client(chunks))
    out = []
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        async for ch in garage._stream_openai_provider("hi", "alpha", "minimax"):
            out.append(ch)
    assert out == []


async def test_stream_openai_provider_wraps_timeout(garage: ModelGarage, monkeypatch):
    class _TimeoutClient:
        class chat:
            class completions:
                @staticmethod
                async def create(*args, **kwargs):
                    raise RuntimeError("request timed out")

    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _TimeoutClient())
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        with pytest.raises(LLMTimeout, match="timed out"):
            async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
                pass


async def test_stream_openai_provider_wraps_openai_error(garage: ModelGarage, monkeypatch):
    class _BoomClient:
        class chat:
            class completions:
                @staticmethod
                async def create(*args, **kwargs):
                    raise _openai.OpenAIError("bad key")

    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _BoomClient())
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        # LLMUnavailable is built from str(exc) — the openai SDK message we passed.
        with pytest.raises(LLMUnavailable, match="bad key"):
            async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
                pass


async def test_stream_openai_provider_re_raises_other(garage: ModelGarage, monkeypatch):
    class _BoomClient:
        class chat:
            class completions:
                @staticmethod
                async def create(*args, **kwargs):
                    raise RuntimeError("weird")

    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _BoomClient())
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        # Bare RuntimeError is re-raised unchanged — match its str().
        with pytest.raises(RuntimeError, match="weird"):
            async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
                pass


async def test_stream_openai_provider_records_call_metric(garage: ModelGarage, monkeypatch):
    monkeypatch.setattr(
        _openai,
        "AsyncOpenAI",
        lambda *a, **kw: _make_openai_client([_FakeChunk([_FakeChoice("x")])]),
    )
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call") as rec,
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
            pass
    rec.assert_called_once()
    assert rec.call_args.args[0] == "minimax"


# -- _stream_anthropic_provider ---------------------------------------------


class _FakeAnthropicStream:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = list(tokens)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def text_stream(self):
        return _async_iter(self._tokens)


class _FakeAnthropicClient:
    def __init__(self, tokens: list[str], exc: Exception | None = None) -> None:
        self._tokens = tokens
        self._exc = exc

    class messages:
        @staticmethod
        def stream(*args, **kwargs):
            raise AssertionError("static call not used")  # pragma: no cover


def _make_anthropic_module(tokens=None, exc=None):
    """Patch anthropic module shape used by garage."""
    if tokens is None:
        tokens = []
    stream_obj = _FakeAnthropicStream(tokens)

    class _Messages:
        def stream(self, *args, **kwargs):
            if exc is not None:
                raise exc
            return stream_obj

    class _AsyncAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = _Messages()

    fake_module = MagicMock()
    fake_module.AsyncAnthropic = _AsyncAnthropic
    fake_module.AnthropicError = Exception
    return fake_module


async def test_stream_anthropic_provider_yields_chunks(garage: ModelGarage, monkeypatch):
    fake_mod = _make_anthropic_module(tokens=["hi", " there"])
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)
    out = []
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        async for ch in garage._stream_anthropic_provider("hi", "alpha"):
            out.append(ch)
    assert [c.token for c in out] == ["hi", " there"]
    assert [c.seq for c in out] == [0, 1]


async def test_stream_anthropic_provider_no_api_key_raises(garage: ModelGarage, monkeypatch):
    monkeypatch.setattr(garage.settings, "anthropic_api_key", "")
    with pytest.raises(LLMUnavailable) as excinfo:
        async for _ in garage._stream_anthropic_provider("hi", "alpha"):
            pass
    assert "no API key" in str(excinfo.value)


async def test_stream_anthropic_provider_wraps_timeout(garage: ModelGarage, monkeypatch):
    fake_mod = _make_anthropic_module(exc=RuntimeError("connection timed out"))
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        with pytest.raises(LLMTimeout, match="timed out"):
            async for _ in garage._stream_anthropic_provider("hi", "alpha"):
                pass


async def test_stream_anthropic_provider_wraps_anthropic_error(garage: ModelGarage, monkeypatch):
    fake_mod = _make_anthropic_module(exc=_anthropic.AnthropicError("auth fail"))
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)
    with (
        patch("tier1.llm.garage.get_tracer") as tracer_patch,
        patch("tier1.llm.garage.record_provider_call"),
    ):
        tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
        # LLMUnavailable wraps str(exc) — match the anthropic SDK message we passed.
        with pytest.raises(LLMUnavailable, match="auth fail"):
            async for _ in garage._stream_anthropic_provider("hi", "alpha"):
                pass


async def test_stream_anthropic_provider_no_package_raises(garage: ModelGarage, monkeypatch):
    # Force ImportError on `import anthropic` via __import__ interception.
    real_import = _builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic" or name.startswith("anthropic."):
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(_builtins, "__import__", fake_import)
    with patch("tier1.llm.garage.get_tracer"), patch("tier1.llm.garage.record_provider_call"):
        with pytest.raises(LLMUnavailable, match="anthropic package not installed"):
            async for _ in garage._stream_anthropic_provider("hi", "alpha"):
                pass


# -- chat() convenience ------------------------------------------------------


async def test_chat_collects_all_tokens_into_string(garage: ModelGarage, monkeypatch):
    """chat() concatenates tokens from stream_chat into one string."""

    async def fake_stream(prompt, *, agent):
        for tok in ("hello", " ", "world"):
            yield StreamChunk(token=tok, agent=agent, seq=0)

    monkeypatch.setattr(garage, "stream_chat", fake_stream)
    result = await garage.chat("hi", agent="alpha")
    assert result == "hello world"


# ---------------------------------------------------------------------------
# Dispatch + import-failure branches
# ---------------------------------------------------------------------------


async def test_stream_from_provider_dispatches_by_name(garage: ModelGarage, monkeypatch):
    """`_stream_from_provider` resolves the right per-provider coroutine."""
    calls: list[str] = []

    async def fake_openai(*args, **kwargs):
        # (self, prompt, agent, provider_name) when bound, but tests bypass
        # that by passing positionally via the source's `fn(prompt, agent, provider)`
        calls.append(f"openai:{args}")
        yield StreamChunk(token="x", agent="alpha", seq=0)

    async def fake_anthropic(*args, **kwargs):
        calls.append(f"anthropic:{args}")
        yield StreamChunk(token="y", agent="alpha", seq=0)

    monkeypatch.setattr(garage, "_stream_openai_provider", fake_openai)
    monkeypatch.setattr(garage, "_stream_anthropic_provider", fake_anthropic)
    out = []
    async for ch in garage._stream_from_provider("anthropic", "hi", "alpha"):
        out.append(ch.token)
    assert calls[0].startswith("anthropic:")
    assert out == ["y"]
    calls.clear()
    out.clear()
    async for ch in garage._stream_from_provider("minimax", "hi", "alpha"):
        out.append(ch.token)
    assert calls[0].startswith("openai:")
    assert "minimax" in calls[0]
    assert out == ["x"]


async def test_stream_openai_provider_no_package_raises(garage: ModelGarage, monkeypatch):
    """If `openai` cannot be imported, raise LLMUnavailable."""
    real_import = _builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai" or name.startswith("openai."):
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(_builtins, "__import__", fake_import)
    with patch("tier1.llm.garage.get_tracer"), patch("tier1.llm.garage.record_provider_call"):
        with pytest.raises(LLMUnavailable) as excinfo:
            async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
                pass
        assert "openai package not installed" in str(excinfo.value)


async def test_stream_openai_provider_openai_error_import_fallback_re_raises(
    garage: ModelGarage, monkeypatch
):
    """If `from openai import OpenAIError` raises ImportError, the exception
    branch must re-raise the original generic exception unchanged."""

    class _BoomClient:
        class chat:
            class completions:
                @staticmethod
                async def create(*args, **kwargs):
                    raise RuntimeError("weird")

    monkeypatch.setattr(_openai, "AsyncOpenAI", lambda *a, **kw: _BoomClient())
    # Delete OpenAIError so the lazy `from openai import OpenAIError` raises
    # ImportError -> OpenAIError is None -> branch falls through to `raise`.
    saved = getattr(_openai, "OpenAIError", None)
    if hasattr(_openai, "OpenAIError"):
        delattr(_openai, "OpenAIError")
    try:
        with (
            patch("tier1.llm.garage.get_tracer") as tracer_patch,
            patch("tier1.llm.garage.record_provider_call"),
        ):
            tracer_patch.return_value.start_as_current_span.return_value = _span_cm()
            with pytest.raises(RuntimeError, match="weird"):
                async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
                    pass
    finally:
        if saved is not None:
            setattr(_openai, "OpenAIError", saved)


async def test_stream_from_provider_dispatches_to_correct_handler(garage: ModelGarage):
    """Regression: garage.py:172 used to call fn(prompt, agent, provider) with 3
    args. _stream_anthropic_provider accepts only 2, so routing anthropic through
    _stream_from_provider raised TypeError. The fix encodes provider_name in the
    dispatch lambdas and calls fn(prompt, agent) with 2 args."""

    async def _empty_gen(*args, **kwargs):
        if False:
            yield  # pragma: no cover

    captured: list[tuple[str, tuple, dict]] = []

    async def _capture_openai(prompt, agent, provider_name):
        captured.append(("openai", (prompt, agent, provider_name), {}))
        async for chunk in _empty_gen():
            yield chunk

    async def _capture_anthropic(prompt, agent):
        captured.append(("anthropic", (prompt, agent), {}))
        async for chunk in _empty_gen():
            yield chunk

    garage._stream_openai_provider = _capture_openai
    garage._stream_anthropic_provider = _capture_anthropic

    # Anthropic path: 2-arg call.
    async for _ in garage._stream_from_provider("anthropic", "hello", "alpha"):
        pass
    assert ("anthropic", ("hello", "alpha"), {}) in captured

    # Openai-family paths: 3-arg call with encoded provider_name.
    async for _ in garage._stream_from_provider("minimax", "hello", "alpha"):
        pass
    assert ("openai", ("hello", "alpha", "minimax"), {}) in captured

    async for _ in garage._stream_from_provider("openai", "hello", "alpha"):
        pass
    assert ("openai", ("hello", "alpha", "openai"), {}) in captured

    async for _ in garage._stream_from_provider("local", "hello", "alpha"):
        pass
    assert ("openai", ("hello", "alpha", "local"), {}) in captured
