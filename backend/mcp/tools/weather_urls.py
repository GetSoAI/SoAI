"""SoAI - MCP weather provider URL builders [backend/mcp/tools/weather_urls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_weather_forecast_url", "build_weather_geocoding_url")

_CURRENT_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)
_DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "relative_humidity_2m_mean",
    "cloud_cover_mean",
)
_HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "is_day",
)


def build_weather_geocoding_url(base_url: str, location: str, country_code: str | None) -> str:
    query: dict[str, str] = {
        "name": location,
        "count": "1",
        "language": "en",
        "format": "json",
    }
    if country_code is not None:
        query["countryCode"] = country_code
    return f"{base_url}/v1/search?{urlencode(query)}"


def build_weather_forecast_url(
    base_url: str,
    location: JSONDict,
    unit_system: str,
    *,
    forecast_days: int,
    hourly_hours: int,
) -> str:
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, int | float)
        or not isinstance(longitude, int | float)
    ):
        raise MCPToolError(-32603, "Weather provider returned invalid location coordinates.")
    latitude_value = float(latitude)
    longitude_value = float(longitude)
    if not math.isfinite(latitude_value) or not math.isfinite(longitude_value):
        raise MCPToolError(-32603, "Weather provider returned invalid location coordinates.")
    temperature_unit = "fahrenheit" if unit_system == "imperial" else "celsius"
    wind_speed_unit = "mph" if unit_system == "imperial" else "kmh"
    query: dict[str, str] = {
        "latitude": str(latitude_value),
        "longitude": str(longitude_value),
        "current": ",".join(_CURRENT_VARIABLES),
        "daily": ",".join(_DAILY_VARIABLES),
        "temperature_unit": temperature_unit,
        "wind_speed_unit": wind_speed_unit,
        "precipitation_unit": "inch" if unit_system == "imperial" else "mm",
        "timezone": "auto",
        "forecast_days": str(int(forecast_days)),
    }
    if hourly_hours > 0:
        query["hourly"] = ",".join(_HOURLY_VARIABLES)
        query["forecast_hours"] = str(int(hourly_hours))
    return f"{base_url}/v1/forecast?{urlencode(query)}"
