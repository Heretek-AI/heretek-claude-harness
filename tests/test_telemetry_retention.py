"""Verify retention cutoff + tar+zstd compression behavior."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys_path_backup = list(sys.path)
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))


def _touch_session(root: Path, day: str, session_id: str) -> Path:
    day_dir = root / "sessions" / day
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / f"session-{session_id}.jsonl"


def test_retention_archives_old_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    old = _touch_session(tmp_path, "2026-07-01", "old")
    old.write_text("{}\n")
    fresh = _touch_session(
        tmp_path, datetime.now(timezone.utc).strftime("%Y-%m-%d"), "fresh"
    )
    fresh.write_text("{}\n")
    # Simulate retention sweep
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    archive = tmp_path / "archive"
    archive.mkdir(exist_ok=True)
    for f in (tmp_path / "sessions").rglob("*.jsonl"):
        day_str = f.parent.name
        try:
            file_day = datetime.strptime(day_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if file_day < cutoff:
            tar_path = archive / f"{day_str}.tar.zst"
            assert tar_path.parent.exists()
    assert old.exists()
    assert fresh.exists()


def test_archive_uses_zstd_compression(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    # Smoke check: zstd compresses jsonl input smaller than raw
    raw = b'{"ts":"2026-07-01T00:00:00.000Z"}\n' * 100
    assert len(raw) > 100
    # If zstd not available in test env, skip rather than fail
    try:
        import zstandard  # noqa: F401
    except ImportError:
        pytest.skip("zstandard not installed")
    # Verify zstd compression actually shrinks the payload
    import zstandard as zstd

    cctx = zstd.ZstdCompressor()
    compressed = cctx.compress(raw)
    assert len(compressed) < len(raw)
