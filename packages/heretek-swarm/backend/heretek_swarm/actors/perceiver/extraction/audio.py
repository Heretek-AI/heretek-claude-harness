"""
Audio-modality extraction — re-exports the canonical
audio helpers from :mod:`heretek_swarm.actors.perceiver.extraction`.

Phase 2.7 of PLAN.md (split perceiver extraction by
modality). The audit recommends splitting
``actors/perceiver/agent.py`` (1,607 LOC) into
``extraction/{image,audio,video,document,sensor}.py``.

The audio helpers are pure: they decode base64 data,
infer MIME type, and provide a file-extension mapping.
The LLM-driven audio description (e.g. Whisper
transcription) lives in the agent because it depends on
``self.swarms_agent.llm``; this module is the home for
the pure helpers.

Backwards compatibility: the legacy methods on
``PerceiverAgent`` (``_decode_audio_bytes``,
``_audio_suffix_from_format``, ``_extract_audio_features``)
still work unchanged.
"""

from __future__ import annotations

from heretek_swarm.actors.perceiver.extraction import (  # noqa: F401
    audio_suffix_from_format,
    decode_audio_bytes,
)


__all__ = [
    "audio_suffix_from_format",
    "decode_audio_bytes",
]
