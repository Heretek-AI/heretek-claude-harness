"""
Video-modality extraction — re-exports the canonical video
helpers from :mod:`heretek_swarm.actors.perceiver.extraction`.

Phase 2.7 of PLAN.md (split perceiver extraction by
modality). The video helpers are pure: they decode base64
data, infer MIME type, parse the ``r_frame_rate`` ffprobe
output, and provide a file-extension mapping.

The agent's ``_extract_video_features`` method uses these
helpers plus an ``ffprobe`` subprocess call; the subprocess
is left in the agent because it depends on agent config
(timeouts, format hints) and shell-out semantics.

Backwards compatibility: the legacy methods on
``PerceiverAgent`` (``_decode_video_bytes``,
``_video_suffix_from_format``, ``_parse_r_frame_rate``,
``_extract_video_features``) still work unchanged.
"""

from __future__ import annotations

from heretek_swarm.actors.perceiver.extraction import (  # noqa: F401
    decode_video_bytes,
    parse_r_frame_rate,
    video_suffix_from_format,
)


__all__ = [
    "decode_video_bytes",
    "parse_r_frame_rate",
    "video_suffix_from_format",
]
