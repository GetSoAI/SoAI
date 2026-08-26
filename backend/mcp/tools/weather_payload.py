"""SoAI - MCP weather provider payload parsing [backend/mcp/tools/weather_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from mcp.tools.error import MCPToolError
from mcp.tools.weather_conditions import build_weather_condition_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_weather_result_payload", "resolve_geocoding_match")


def _require_dict(value: JSONValue, field_name: str) -> JSONDict:
    payload = coerce_json_dict(value)
    if payload is None:
        raise MCPToolError(-32603, f"Weather provider returned invalid {field_name} data.")
    return payload


def _require_string(payload: JSONDict, field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    return value.strip()


def _optional_string(payload: JSONDict, field_name: str) -> str | None:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _require_float(payload: JSONDict, field_name: str) -> float:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise MCPToolError(-32603, f"Weather provider response is invalid for {field_name}.")
    return parsed


def _require_int(payload: JSONDict, field_name: str) -> int:
    value = payload.get(field_name)
    if not is_strict_int(value):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    return int(value)


def _require_binary_flag(payload: JSONDict, field_name: str) -> bool:
    value = _require_int(payload, field_name)
    if value not in {0, 1}:
        raise MCPToolError(-32603, f"Weather provider response is invalid for {field_name}.")
    return value == 1


def _require_series(payload: JSONDict, field_name: str) -> list[JSONValue]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    return list(value)


def _series_string(series: list[JSONValue], index: int, field_name: str) -> str:
    if index >= len(series) or not isinstance(series[index], str) or not str(series[index]).strip():
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    return str(series[index]).strip()


def _series_float(series: list[JSONValue], index: int, field_name: str) -> float:
    if index >= len(series):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    value = series[index]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise MCPToolError(-32603, f"Weather provider response is invalid for {field_name}.")
    return parsed


def _series_int(series: list[JSONValue], index: int, field_name: str) -> int:
    if index >= len(series):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    value = series[index]
    if not is_strict_int(value):
        raise MCPToolError(-32603, f"Weather provider response is missing {field_name}.")
    return int(value)


def _series_binary_flag(series: list[JSONValue], index: int, field_name: str) -> bool:
    value = _series_int(series, index, field_name)
    if value not in {0, 1}:
        raise MCPToolError(-32603, f"Weather provider response is invalid for {field_name}.")
    return value == 1


def resolve_geocoding_match(payload: JSONDict) -> JSONDict:
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise MCPToolError(-32603, "Weather provider could not find that location.")
    first = coerce_json_dict(results[0])
    if first is None:
        raise MCPToolError(-32603, "Weather provider returned invalid location data.")
    return first


def _build_current_payload(current: JSONDict) -> JSONDict:
    weather_code = _require_int(current, "weather_code")
    return {
        "time": _require_string(current, "time"),
        "temperature": _require_float(current, "temperature_2m"),
        "apparent_temperature": _require_float(current, "apparent_temperature"),
        "relative_humidity": _require_int(current, "relative_humidity_2m"),
        "is_day": _require_binary_flag(current, "is_day"),
        "precipitation": _require_float(current, "precipitation"),
        "rain": _require_float(current, "rain"),
        "showers": _require_float(current, "showers"),
        "snowfall": _require_float(current, "snowfall"),
        "cloud_cover": _require_int(current, "cloud_cover"),
        "surface_pressure": _require_float(current, "surface_pressure"),
        "wind_speed": _require_float(current, "wind_speed_10m"),
        "wind_direction": _require_int(current, "wind_direction_10m"),
        "wind_gusts": _require_float(current, "wind_gusts_10m"),
        **build_weather_condition_payload(weather_code),
    }


def _build_daily_payload(daily: JSONDict, *, forecast_days: int) -> list[JSONDict]:
    dates = _require_series(daily, "time")
    codes = _require_series(daily, "weather_code")
    max_temperatures = _require_series(daily, "temperature_2m_max")
    min_temperatures = _require_series(daily, "temperature_2m_min")
    apparent_max = _require_series(daily, "apparent_temperature_max")
    apparent_min = _require_series(daily, "apparent_temperature_min")
    precipitation_probabilities = _require_series(daily, "precipitation_probability_max")
    wind_speed_max = _require_series(daily, "wind_speed_10m_max")
    wind_direction_dominant = _require_series(daily, "wind_direction_10m_dominant")
    relative_humidity_mean = _require_series(daily, "relative_humidity_2m_mean")
    cloud_cover_mean = _require_series(daily, "cloud_cover_mean")
    entries: list[JSONDict] = []
    for index in range(min(forecast_days, len(dates))):
        weather_code = _series_int(codes, index, "daily.weather_code")
        entries.append(
            {
                "date": _series_string(dates, index, "daily.time"),
                "temperature_max": _series_float(
                    max_temperatures,
                    index,
                    "daily.temperature_2m_max",
                ),
                "temperature_min": _series_float(
                    min_temperatures,
                    index,
                    "daily.temperature_2m_min",
                ),
                "apparent_temperature_max": _series_float(
                    apparent_max,
                    index,
                    "daily.apparent_temperature_max",
                ),
                "apparent_temperature_min": _series_float(
                    apparent_min,
                    index,
                    "daily.apparent_temperature_min",
                ),
                "precipitation_probability": _series_int(
                    precipitation_probabilities,
                    index,
                    "daily.precipitation_probability_max",
                ),
                "wind_speed_max": _series_float(wind_speed_max, index, "daily.wind_speed_10m_max"),
                "wind_direction_dominant": _series_int(
                    wind_direction_dominant,
                    index,
                    "daily.wind_direction_10m_dominant",
                ),
                "relative_humidity_mean": _series_int(
                    relative_humidity_mean,
                    index,
                    "daily.relative_humidity_2m_mean",
                ),
                "cloud_cover_mean": _series_int(cloud_cover_mean, index, "daily.cloud_cover_mean"),
                **build_weather_condition_payload(weather_code),
            },
        )
    if not entries:
        raise MCPToolError(-32603, "Weather provider response is missing daily forecast data.")
    return entries


def _build_hourly_payload(hourly: JSONDict | None, *, hourly_hours: int) -> list[JSONDict]:
    if hourly is None or hourly_hours <= 0:
        return []
    times = _require_series(hourly, "time")
    temperatures = _require_series(hourly, "temperature_2m")
    precipitation_probabilities = _require_series(hourly, "precipitation_probability")
    precipitations = _require_series(hourly, "precipitation")
    codes = _require_series(hourly, "weather_code")
    wind_speeds = _require_series(hourly, "wind_speed_10m")
    is_day_series = _require_series(hourly, "is_day")
    entries: list[JSONDict] = []
    for index in range(min(hourly_hours, len(times))):
        weather_code = _series_int(codes, index, "hourly.weather_code")
        entries.append(
            {
                "time": _series_string(times, index, "hourly.time"),
                "temperature": _series_float(temperatures, index, "hourly.temperature_2m"),
                "precipitation_probability": _series_int(
                    precipitation_probabilities,
                    index,
                    "hourly.precipitation_probability",
                ),
                "precipitation": _series_float(precipitations, index, "hourly.precipitation"),
                "wind_speed": _series_float(wind_speeds, index, "hourly.wind_speed_10m"),
                "is_day": _series_binary_flag(is_day_series, index, "hourly.is_day"),
                **build_weather_condition_payload(weather_code),
            },
        )
    return entries


def build_weather_result_payload(
    *,
    location: JSONDict,
    forecast: JSONDict,
    unit_system: str,
    elapsed_ms: int,
    forecast_days: int,
    hourly_hours: int,
) -> JSONDict:
    current = _require_dict(forecast.get("current"), "current weather")
    daily = _require_dict(forecast.get("daily"), "daily weather")
    hourly = coerce_json_dict(forecast.get("hourly"))
    payload: JSONDict = {
        "provider": "open_meteo",
        "location_name": _require_string(location, "name"),
        "country": _require_string(location, "country"),
        "country_code": _require_string(location, "country_code"),
        "latitude": _require_float(location, "latitude"),
        "longitude": _require_float(location, "longitude"),
        "timezone": _require_string(forecast, "timezone"),
        "unit_system": unit_system,
        "current": _build_current_payload(current),
        "daily": _build_daily_payload(daily, forecast_days=forecast_days),
        "elapsed_ms": int(elapsed_ms),
    }
    admin1 = _optional_string(location, "admin1")
    if admin1 is not None:
        payload["admin1"] = admin1
    hourly_entries = _build_hourly_payload(hourly, hourly_hours=hourly_hours)
    if hourly_entries:
        payload["hourly"] = hourly_entries
    return payload
