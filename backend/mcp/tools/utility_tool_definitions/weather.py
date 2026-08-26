"""SoAI - MCP utility tool definition: weather [backend/mcp/tools/utility_tool_definitions/weather.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_WEATHER

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_weather_tool_definitions",)


def _condition_schema() -> JSONDict:
    return {
        "weather_code": {"type": "integer"},
        "condition_type": {"type": "string"},
        "condition_text": {"type": "string"},
    }


def _hourly_item_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "time": {"type": "string"},
            "temperature": {"type": "number"},
            "precipitation_probability": {"type": "integer"},
            "precipitation": {"type": "number"},
            "wind_speed": {"type": "number"},
            "is_day": {"type": "boolean"},
            **_condition_schema(),
        },
    }


def build_weather_tool_definitions() -> dict[str, JSONDict]:
    return {
        "weather": {
            "title": "Weather",
            "description": (
                "Get current conditions and a daily forecast (1-14 days, default 3) for a "
                "user-provided location using the configured no-key Open-Meteo-compatible "
                "endpoints, optionally with an hourly forecast (up to 48 hours). Use this for "
                "weather questions, include country_code when a location is ambiguous, set "
                "units to imperial only when the user asks for Fahrenheit or imperial units, "
                "set forecast_days to the asked window, and set hourly_hours when intra-day "
                "detail is requested."
            ),
            "icons": [build_tool_icon_entry(ICON_WEATHER)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["location"],
                "properties": {
                    "location": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 200,
                        "description": "City, place, or address to look up.",
                    },
                    "units": {
                        "type": "string",
                        "enum": ["metric", "imperial"],
                        "description": "Unit system. Defaults to metric.",
                    },
                    "country_code": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 2,
                        "description": "Optional ISO alpha-2 country code to disambiguate location.",
                    },
                    "forecast_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 14,
                        "description": (
                            "Days of daily forecast to include (1-14). Defaults to 3. Use 1 for "
                            "current conditions only; 7 for a week ahead."
                        ),
                    },
                    "hourly_hours": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 48,
                        "description": (
                            "Hours of hour-by-hour forecast starting from now (0-48). Defaults "
                            "to 0 (disabled). Use 12-24 for 'later today / tomorrow' style "
                            "questions."
                        ),
                    },
                },
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "provider",
                    "location_name",
                    "country",
                    "country_code",
                    "latitude",
                    "longitude",
                    "timezone",
                    "unit_system",
                    "current",
                    "daily",
                    "elapsed_ms",
                ],
                "properties": {
                    "provider": {"type": "string"},
                    "location_name": {"type": "string"},
                    "admin1": {"type": "string"},
                    "country": {"type": "string"},
                    "country_code": {"type": "string"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "timezone": {"type": "string"},
                    "unit_system": {"type": "string", "enum": ["metric", "imperial"]},
                    "current": {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "time": {"type": "string"},
                            "temperature": {"type": "number"},
                            "apparent_temperature": {"type": "number"},
                            "relative_humidity": {"type": "integer"},
                            "is_day": {"type": "boolean"},
                            "precipitation": {"type": "number"},
                            "wind_speed": {"type": "number"},
                            "wind_direction": {"type": "integer"},
                            "wind_gusts": {"type": "number"},
                            **_condition_schema(),
                        },
                    },
                    "daily": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "date": {"type": "string"},
                                "temperature_max": {"type": "number"},
                                "temperature_min": {"type": "number"},
                                "apparent_temperature_max": {"type": "number"},
                                "apparent_temperature_min": {"type": "number"},
                                "precipitation_probability": {"type": "integer"},
                                "wind_speed_max": {"type": "number"},
                                "wind_direction_dominant": {"type": "integer"},
                                "relative_humidity_mean": {"type": "integer"},
                                "cloud_cover_mean": {"type": "integer"},
                                **_condition_schema(),
                            },
                        },
                    },
                    "hourly": {
                        "type": "array",
                        "items": _hourly_item_schema(),
                    },
                    "elapsed_ms": {"type": "integer"},
                },
            },
            "annotations": {
                **build_tool_annotation_flags(read_only=True, open_world=True),
                "requiresApprovalHint": False,
            },
        },
    }
