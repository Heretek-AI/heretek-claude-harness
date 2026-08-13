"""
Pure content-extraction helpers for the Perceiver agent.

Extracted from ``actors/perceiver/agent.py`` as part of Phase 2.3
of PLAN.md (§1.4 god-class extraction — 1,731-LOC Perceiver agent
that was 70% content extraction, 30% actor behavior).

This module holds the parts of the Perceiver's content-extraction
pipeline that have **no agent state dependencies** (no
``self.logger``, ``self.swarms_agent``, ``self.llm``, …). The
agent's ``_extract_*_features`` methods become thin delegates
to these functions; the agent still owns the LLM-driven paths
(``_try_describe_image_llm`` etc.) and the dispatcher
(``_extract_modality_features``).

Backwards compatibility: every public function is also re-exported
under the legacy ``PerceiverAgent._<name>`` static-method shape
via a thin ``@staticmethod`` wrapper in ``agent.py``.

Why a separate module
---------------------
1. **Smaller agent file**: the audit's exit criterion for Phase 2
   is "largest file < 1,000 LOC" and the agent was 1,731 LOC.
   Moving the pure extractors reduces it.
2. **Testability**: the pure extractors can be unit-tested in
   isolation without spinning up an agent.
3. **Reusability**: the same MIME-suffix / byte-decode / frame-
   rate parsing helpers are useful in other surfaces (the
   rag/document_processor pipeline, the actor_workspace
   ingest, etc.).
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

# Optional PIL/Pillow for image feature extraction
_PIL_AVAILABLE = False
try:
    from PIL import Image as _PIL_Image  # type: ignore[import-untyped]
    from PIL import ImageStat as _PIL_ImageStat  # type: ignore[import-untyped]
    Image = _PIL_Image
    ImageStat = _PIL_ImageStat
    _PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OCTET_STREAM_MIME = "application/octet-stream"


# ---------------------------------------------------------------------------
# Modality detection
# ---------------------------------------------------------------------------


def detect_bytes_modality(data: bytes) -> str:
    """Detect modality from byte magic numbers.

    The Perceiver uses a 6-way enum (TEXT / IMAGE / AUDIO / VIDEO /
    DOCUMENT / SENSOR). For raw bytes we can only tell apart the
    three that have magic-number signatures: JPEG, PNG, WAV.
    Everything else falls back to TEXT — the agent's downstream
    classifier can re-route it.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image"  # JPEG
    if data.startswith(b"\x89PNG"):
        return "image"  # PNG
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio"  # WAV
    return "text"


# ---------------------------------------------------------------------------
# Image extractors
# ---------------------------------------------------------------------------


def decode_image_bytes(image_data: Any) -> bytes:
    """Decode ``image_data`` to raw bytes regardless of input format.

    Handles:
    - ``data:image/xxx;base64,...`` data URLs
    - plain base64 strings
    - ``bytes``
    """
    if isinstance(image_data, bytes):
        return image_data
    if not isinstance(image_data, str):
        return b""
    payload = image_data
    if payload.startswith("data:"):
        # Strip the "data:image/xxx;base64," prefix
        try:
            payload = payload.split(",", 1)[1]
        except IndexError:
            payload = ""
    try:
        return base64.b64decode(payload)
    except Exception:
        return image_data.encode("utf-8")


def extract_image_pil(image_bytes: bytes) -> dict[str, Any]:
    """Extract image features using PIL/Pillow.

    Returns a dict with size, mode, basic stats. Returns
    empty dict on any error (PIL missing, decode failure,
    unsupported format).
    """
    if not _PIL_AVAILABLE or Image is None or ImageStat is None:
        logger.warning("PIL not available; cannot extract image features")
        return {}

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()

        stat = ImageStat.Stat(img)

        width, height = img.size
        mode = img.mode
        extrema = stat.extrema
        mean = stat.mean

        return {
            "width": width,
            "height": height,
            "mode": mode,
            "extrema": [list(e) for e in extrema],
            "mean": list(mean),
            "format": img.format,
        }
    except Exception as exc:
        logger.exception("PIL image feature extraction failed", error=str(exc))
        return {}


def detect_image_mime(image_data: Any) -> str:
    """Infer a MIME type string from the input shape."""
    if isinstance(image_data, str) and image_data.startswith("data:"):
        try:
            return image_data.split(":")[1].split(";")[0]
        except IndexError:
            return "unknown"
    if isinstance(image_data, bytes):
        # Sniff magic bytes
        if image_data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_data.startswith(b"\x89PNG"):
            return "image/png"
        if image_data.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        return OCTET_STREAM_MIME
    return "unknown"


def merge_image_features(
    base: dict[str, Any],
    pil_features: dict[str, Any],
    llm_description: str | None,
) -> dict[str, Any]:
    """Combine base image metadata, PIL-derived features, and the
    optional LLM description into a single feature dict."""
    result = dict(base)
    if pil_features:
        result.update(pil_features)
        result["description"] = llm_description or ""
        result["analyzed_by"] = "pil+llm" if llm_description else "pil"
    elif llm_description:
        result["description"] = llm_description
        result["analyzed_by"] = "llm"
    else:
        result["analyzed_by"] = "metadata"
    return result


# ---------------------------------------------------------------------------
# Audio extractors
# ---------------------------------------------------------------------------


def decode_audio_bytes(audio_data: Any) -> tuple[bytes, str]:
    """Decode ``audio_data`` to raw bytes and infer a MIME type.

    Returns ``(bytes, mime_type)``.
    """
    if isinstance(audio_data, bytes):
        return audio_data, OCTET_STREAM_MIME
    if not isinstance(audio_data, str):
        return b"", "unknown"

    payload = audio_data
    mime_type = OCTET_STREAM_MIME
    if payload.startswith("data:"):
        try:
            header, payload = payload.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
        except (IndexError, ValueError):
            pass

    try:
        return base64.b64decode(payload), mime_type
    except Exception:
        return audio_data.encode("utf-8"), mime_type


_AUDIO_MIME_EXT_MAP: dict[str, str] = {
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/ogg": ".ogg",
    "audio/vorbis": ".ogg",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
    "audio/x-aac": ".aac",
    "audio/webm": ".webm",
}


def audio_suffix_from_format(
    format_hint: str | None, mime_type: str
) -> str:
    """Return a file extension (with dot) for a known audio format or mime."""
    format_lower = (format_hint or "").lower()
    if format_lower in {"wav", "mp3", "ogg", "flac", "aac", "webm"}:
        return f".{format_lower}"
    if mime_type and mime_type != OCTET_STREAM_MIME:
        for mime_key, ext in _AUDIO_MIME_EXT_MAP.items():
            if mime_type == mime_key or mime_type.startswith(mime_key):
                return ext
    if format_lower:
        return f".{format_lower}"
    return ".audio"


# ---------------------------------------------------------------------------
# Video extractors
# ---------------------------------------------------------------------------


def decode_video_bytes(video_data: Any) -> tuple[bytes, str]:
    """Decode ``video_data`` to raw bytes and infer a MIME type.

    Returns ``(bytes, mime_type)``.
    """
    if isinstance(video_data, bytes):
        return video_data, OCTET_STREAM_MIME
    if not isinstance(video_data, str):
        return b"", "unknown"

    payload = video_data
    mime_type = OCTET_STREAM_MIME
    if payload.startswith("data:"):
        try:
            header, payload = payload.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
        except (IndexError, ValueError):
            pass

    try:
        return base64.b64decode(payload), mime_type
    except Exception:
        return video_data.encode("utf-8"), mime_type


_VIDEO_MIME_EXT_MAP: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/mpeg": ".mpg",
    "video/avi": ".avi",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}


def video_suffix_from_format(
    format_hint: str | None, mime_type: str
) -> str:
    """Return a file extension (with dot) for a known video format or mime."""
    format_lower = (format_hint or "").lower()
    if format_lower in {"mp4", "avi", "mov", "webm", "mkv", "mpg", "mpeg"}:
        return f".{format_lower}"
    if mime_type and mime_type != OCTET_STREAM_MIME:
        for mime_key, ext in _VIDEO_MIME_EXT_MAP.items():
            if mime_type == mime_key or mime_type.startswith(mime_key):
                return ext
    if format_lower:
        return f".{format_lower}"
    return ".video"


def parse_r_frame_rate(r_frame_rate: str | None) -> float | None:
    """Convert ``r_frame_rate`` string (e.g. "30/1" or "30000/1001") to float.

    Returns None when input is empty, malformed, or zero-denominator.
    """
    if not r_frame_rate:
        return None
    try:
        num, denom = r_frame_rate.split("/", 1)
        n = int(num)
        d = int(denom)
        if d == 0:
            return None
        return round(n / d, 2)
    except (ValueError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Text feature extraction
# ---------------------------------------------------------------------------


def extract_text_features(text: str) -> dict[str, Any]:
    """Extract features from text input.

    Returns a dict with character / word / sentence statistics,
    vocabulary richness, and a few format flags (code, JSON, XML).
    """
    if not isinstance(text, str):
        text = str(text)

    # Basic text statistics
    words = text.split()
    sentences = text.replace("!", ".").replace("?", ".").split(".")
    sentences = [s.strip() for s in sentences if s.strip()]

    # Character-level features
    char_count = len(text)
    char_count_no_spaces = len(text.replace(" ", ""))

    # Word-level features
    word_count = len(words)
    avg_word_length = (
        sum(len(w) for w in words) / word_count if word_count > 0 else 0
    )

    # Sentence-level features
    sentence_count = len(sentences)
    avg_sentence_length = (
        word_count / sentence_count if sentence_count > 0 else 0
    )

    # Vocabulary features
    unique_words = {w.lower() for w in words}
    vocabulary_richness = (
        len(unique_words) / word_count if word_count > 0 else 0
    )

    # Detect potential language patterns
    has_code = any(c in text for c in "{}[]()=;") and (
        "function" in text or "def " in text or "import " in text
    )
    has_json = text.strip().startswith(("{", "["))
    has_xml = text.strip().startswith("<")

    return {
        "char_count": char_count,
        "char_count_no_spaces": char_count_no_spaces,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "unique_words": len(unique_words),
        "vocabulary_richness": round(vocabulary_richness, 3),
        "has_code_structure": has_code,
        "has_json_format": has_json,
        "has_xml_format": has_xml,
        "preview": text[:200] if len(text) > 200 else text,
    }


# ---------------------------------------------------------------------------
# Document structure detection
# ---------------------------------------------------------------------------


def detect_text_structure(text: str, fmt: str) -> dict[str, Any]:
    """Detect document structure from text content.

    Returns a ``structure`` dict with format-specific markers.
    """
    structure: dict[str, Any] = {}

    if fmt == "json":
        # Attempt JSON parse — count top-level keys/items
        import json as _json

        try:
            parsed = _json.loads(text)
            if isinstance(parsed, dict):
                structure["json_keys"] = len(parsed)
                structure["json_type"] = "object"
            elif isinstance(parsed, list):
                structure["json_items"] = len(parsed)
                structure["json_type"] = "array"
            else:
                structure["json_type"] = type(parsed).__name__
            structure["json_valid"] = True
        except (_json.JSONDecodeError, ValueError):
            structure["json_valid"] = False

    elif fmt in ("xml", "html"):
        # Count XML/HTML tags with a simple regex
        import re as _re

        tags = _re.findall(r"<\s*/?\s*(\w+)", text)
        if tags:
            tag_counts: dict[str, int] = {}
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
            structure["tag_count"] = len(tags)
            structure["unique_tags"] = len(tag_counts)
            # Show top-5 most frequent tags
            top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
            structure["top_tags"] = dict(top_tags)

    elif fmt == "csv":
        import csv as _csv
        import io as _io

        try:
            reader = _csv.reader(_io.StringIO(text))
            rows = list(reader)
            structure["row_count"] = len(rows)
            if rows:
                structure["column_count"] = len(rows[0])
                structure["header"] = rows[0]
        except _csv.Error:
            structure["csv_valid"] = False
        else:
            structure["csv_valid"] = True

    elif fmt == "markdown":
        # Count markdown structure markers
        structure["heading_count"] = sum(
            1 for line in text.splitlines() if line.strip().startswith("#")
        )
        structure["code_block_count"] = text.count("```") // 2
        structure["link_count"] = text.count("](")

    return structure


__all__ = [
    "OCTET_STREAM_MIME",
    "audio_suffix_from_format",
    "decode_audio_bytes",
    "decode_image_bytes",
    "decode_video_bytes",
    "detect_bytes_modality",
    "detect_image_mime",
    "detect_text_structure",
    "extract_image_pil",
    "extract_sensor_features",
    "extract_text_features",
    "merge_image_features",
    "parse_r_frame_rate",
    "video_suffix_from_format",
]
