"""
Sensor-feature extraction helpers — extracted from
``actors/perceiver/agent.py`` as part of Phase 2.7 of PLAN.md.

The :func:`extract_sensor_features` free function is the
pure value-object path for sensor data: input validation,
basic statistics on numeric values, and a structured return
shape. The agent method ``_extract_sensor_features`` now
delegates here.
"""

from __future__ import annotations

from typing import Any


def extract_sensor_features(sensor_data: dict[str, Any]) -> dict[str, Any]:
    """Extract features from sensor data.

    Returns a structured dict with:
      - ``keys``: the dict's keys (the sensor channels)
      - ``numeric_stats``: min / max / avg / count of the
        numeric values, or an empty dict if the sensor
        data has no numeric values
      - ``analyzed_by``: a marker that the result came from
        this parser

    The function does not raise; non-dict inputs return an
    error dict so the caller can route the failure to the
    agent's error path.
    """
    if not isinstance(sensor_data, dict):
        return {"error": "Sensor data must be a dictionary"}

    # Extract basic statistics from numeric values
    numeric_values: list[float] = []
    for value in sensor_data.values():
        if isinstance(value, (int, float)):
            numeric_values.append(float(value))

    stats: dict[str, float] = {}
    if numeric_values:
        stats = {
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values),
            "count": float(len(numeric_values)),
        }

    return {
        "keys": list(sensor_data.keys()),
        "numeric_stats": stats,
        "analyzed_by": "sensor_parser",
    }


__all__ = ["extract_sensor_features"]
