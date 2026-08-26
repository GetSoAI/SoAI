"""SoAI - MCP weather condition mapping [backend/mcp/tools/weather_conditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_weather_condition_payload",)

_CONDITIONS: tuple[tuple[int, str, str], ...] = (
    (0, "clear", "Clear"),
    (1, "mostly_clear", "Mostly clear"),
    (2, "partly_cloudy", "Partly cloudy"),
    (3, "cloudy", "Cloudy"),
    (45, "fog", "Fog"),
    (48, "fog", "Depositing rime fog"),
    (51, "drizzle", "Light drizzle"),
    (53, "drizzle", "Drizzle"),
    (55, "drizzle", "Heavy drizzle"),
    (56, "freezing_drizzle", "Light freezing drizzle"),
    (57, "freezing_drizzle", "Freezing drizzle"),
    (61, "rain", "Light rain"),
    (63, "rain", "Rain"),
    (65, "rain", "Heavy rain"),
    (66, "freezing_rain", "Light freezing rain"),
    (67, "freezing_rain", "Freezing rain"),
    (71, "snow", "Light snow"),
    (73, "snow", "Snow"),
    (75, "snow", "Heavy snow"),
    (77, "snow", "Snow grains"),
    (80, "showers", "Light rain showers"),
    (81, "showers", "Rain showers"),
    (82, "showers", "Heavy rain showers"),
    (85, "snow", "Light snow showers"),
    (86, "snow", "Heavy snow showers"),
    (95, "thunderstorm", "Thunderstorm"),
    (96, "thunderstorm", "Thunderstorm with light hail"),
    (99, "thunderstorm", "Thunderstorm with hail"),
)


def build_weather_condition_payload(weather_code: int) -> JSONDict:
    normalized_code = int(weather_code)
    condition_type = "unknown"
    text = "Unknown"
    for code, candidate_type, candidate_text in _CONDITIONS:
        if code == normalized_code:
            condition_type = candidate_type
            text = candidate_text
            break
    return {
        "weather_code": normalized_code,
        "condition_type": condition_type,
        "condition_text": text,
    }
