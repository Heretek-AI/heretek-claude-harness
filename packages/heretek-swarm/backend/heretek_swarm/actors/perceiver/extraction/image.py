"""
Image-modality extraction — re-exports the canonical
image helpers from :mod:`heretek_swarm.actors.perceiver.extraction`
and is the namespace for image-specific extensions.

Phase 2.7 of PLAN.md (split perceiver extraction by
modality). The audit's recommendation is to split
``actors/perceiver/agent.py`` (1,607 LOC) into
``extraction/{image,audio,video,document,sensor}.py``.

This commit ships the per-modality namespace. Image
extraction is the simplest modality (no LLM call
involved beyond an optional description), so it's the
first one packaged here.

Backwards compatibility: the legacy methods on
``PerceiverAgent`` (``_extract_image_features``,
``_try_extract_pil``, ``_extract_image_pil``) still work
unchanged. New code should import from this module
directly:

  from heretek_swarm.actors.perceiver.extraction.image import (
      extract_image_pil,
  )
"""

from __future__ import annotations

from heretek_swarm.actors.perceiver.extraction import (  # noqa: F401
    decode_image_bytes,
    detect_image_mime,
    extract_image_pil,
    merge_image_features,
)


def extract_image_summary(image_data: object, format_hint: str | None = None) -> dict[str, object]:
    """Return a single dict summarizing the image's MIME,
    size, base64-decoded byte length, and any PIL-extracted
    features.

    This is a thin convenience wrapper over the canonical
    image helpers that the agent methods use. New code
    that needs an image summary (without going through
    the agent) can call this directly.
    """
    mime_type = detect_image_mime(image_data)
    image_bytes = decode_image_bytes(image_data)
    base: dict[str, object] = {
        "format": format_hint or "unknown",
        "mime_type": mime_type,
        "size_bytes": len(image_bytes),
    }
    pil_features = extract_image_pil(image_bytes)
    return merge_image_features(base, pil_features, None)


__all__ = [
    "decode_image_bytes",
    "detect_image_mime",
    "extract_image_pil",
    "extract_image_summary",
    "merge_image_features",
]
