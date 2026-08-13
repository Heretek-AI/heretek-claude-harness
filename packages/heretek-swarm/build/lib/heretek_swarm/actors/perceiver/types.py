"""Perceiver types — Modality type enumeration."""

from enum import StrEnum


class ModalityType(StrEnum):
    """Supported input modalities."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    SENSOR = "sensor"
