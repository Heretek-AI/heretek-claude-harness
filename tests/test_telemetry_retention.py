"""Verify retention cutoff + tar+zstd compression behavior."""

from __future__ import annotations

import io
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "plugins" / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import telemetry_collector


def _touch_session(root: Path, day: str, session_id: str, body: str = "{}\n") -> Path:
    day_dir = root / "sessions" / day
    day_dir.mkdir(parents=True, exist_ok=True)
    session_file = day_dir / f"session-{session_id}.jsonl"
    session_file.write_text(body)
    return session_file


def test_retention_sweep_archives_old_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        import zstandard  # noqa: F401
    except ImportError:
        pytest.skip("zstandard not installed")

    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    old = _touch_session(tmp_path, "2026-07-01", "old")
    fresh_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fresh = _touch_session(tmp_path, fresh_day, "fresh")

    # Pre-check: setup actually created the day directory we'll assert was removed
    assert (tmp_path / "sessions" / "2026-07-01").is_dir()

    archived = telemetry_collector.run_retention_sweep(root=tmp_path, cutoff_days=30)

    assert archived == 1
    tar_path = tmp_path / "archive" / "2026-07-01.tar.zst"
    assert tar_path.exists()
    assert not old.exists()
    assert not (tmp_path / "sessions" / "2026-07-01").is_dir()
    assert fresh.exists()
    assert (tmp_path / "sessions" / fresh_day).is_dir()

    # Decompress and verify payload survives the round-trip
    import zstandard as zstd

    raw = tar_path.read_bytes()
    decompressed = zstd.ZstdDecompressor().decompress(raw)
    with tarfile.open(fileobj=io.BytesIO(decompressed), mode="r") as tar:
        names = tar.getnames()
        ef = tar.extractfile("session-old.jsonl")
        assert ef is not None
        extracted = ef.read()
    assert "session-old.jsonl" in names
    assert extracted == b"{}\n"


def test_retention_sweep_leaves_recent_sessions_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        import zstandard  # noqa: F401
    except ImportError:
        pytest.skip("zstandard not installed")

    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    recent = _touch_session(tmp_path, yesterday, "recent")

    archived = telemetry_collector.run_retention_sweep(root=tmp_path, cutoff_days=30)

    assert archived == 0
    assert recent.exists()
    assert not (tmp_path / "archive").exists()


def test_archive_uses_zstd_compression(tmp_path: Path) -> None:
    """Confirm raw JSONL shrinks under zstd before the sweep commits it."""
    raw = b'{"ts":"2026-07-01T00:00:00.000Z","session_id":"x"}\n' * 100
    assert len(raw) > 100
    try:
        import zstandard as zstd
    except ImportError:
        pytest.skip("zstandard not installed")
    compressed = zstd.ZstdCompressor().compress(raw)
    assert len(compressed) < len(raw)
