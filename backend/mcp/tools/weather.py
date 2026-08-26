"""SoAI - MCP utility tool handler: weather [backend/mcp/tools/weather.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx2

from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_clamped_int,
    coerce_lenient_positive_int,
)
from mcp.tools.argument_fields import (
    require_allowed_keys,
    require_bounded_string,
    require_string_choice,
)
from mcp.tools.configured_http_endpoint import (
    ConfiguredEndpointNetworkTarget,
    ConfiguredEndpointSpec,
    resolve_configured_endpoint_from_spec,
)
from mcp.tools.error import MCPToolError
from mcp.tools.provider_http import (
    build_provider_http_status_message,
    map_provider_http_exception,
    parse_provider_json_dict,
    read_provider_response_bytes,
)
from mcp.tools.weather_payload import (
    build_weather_result_payload,
    resolve_geocoding_match,
)
from mcp.tools.weather_urls import (
    build_weather_forecast_url,
    build_weather_geocoding_url,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_weather",)

_DEFAULT_GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com"
_DEFAULT_FORECAST_BASE_URL = "https://api.open-meteo.com"
_CONFIG_PREFIX = "TOOLS.MCP.WEATHER"
_ALLOWED_ARGUMENT_KEYS = frozenset(
    {"location", "units", "country_code", "forecast_days", "hourly_hours"},
)
_DEFAULT_FORECAST_DAYS = 3
_MIN_FORECAST_DAYS = 1
_MAX_FORECAST_DAYS = 14
_DEFAULT_HOURLY_HOURS = 0
_MIN_HOURLY_HOURS = 0
_MAX_HOURLY_HOURS = 48


def _parse_country_code(arguments: JSONDict) -> str | None:
    raw_country_code = arguments.get("country_code")
    if raw_country_code is None:
        return None
    country_code = require_bounded_string(raw_country_code, field="country_code", max_length=2)
    if len(country_code) != 2 or not country_code.isalpha():
        raise MCPToolError(-32602, "country_code must be a two-letter ISO country code.")
    return country_code.upper()


def _parse_location(arguments: JSONDict) -> str:
    location = require_bounded_string(arguments.get("location"), field="location", max_length=200)
    if len(location) < 2:
        raise MCPToolError(-32602, "location must be at least 2 characters.")
    return location


def _parse_forecast_days(arguments: JSONDict) -> int:
    raw_value = arguments.get("forecast_days")
    if raw_value is None:
        return _DEFAULT_FORECAST_DAYS
    return coerce_lenient_clamped_int(
        raw_value,
        default=_DEFAULT_FORECAST_DAYS,
        minimum=_MIN_FORECAST_DAYS,
        maximum=_MAX_FORECAST_DAYS,
    )


def _parse_hourly_hours(arguments: JSONDict) -> int:
    raw_value = arguments.get("hourly_hours")
    if raw_value is None:
        return _DEFAULT_HOURLY_HOURS
    return coerce_lenient_clamped_int(
        raw_value,
        default=_DEFAULT_HOURLY_HOURS,
        minimum=_MIN_HOURLY_HOURS,
        maximum=_MAX_HOURLY_HOURS,
    )


def _build_provider_status_error(status_code: int) -> str:
    return build_provider_http_status_message(
        status_code,
        provider_label="Weather provider",
        auth_rejected_message="Weather provider rejected the no-key request.",
        timeout_message="Weather provider timed out while processing the request.",
        rate_limit_message="Weather provider rate limit was reached. Retry later.",
        unavailable_message="Weather provider is temporarily unavailable.",
    )


async def _resolve_network_target(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    config_key: str,
    default_base_url: str,
    source: str,
) -> ConfiguredEndpointNetworkTarget:
    return await resolve_configured_endpoint_from_spec(
        config=utility_tools.config,
        runtime_flags=utility_tools.runtime_flags,
        spec=ConfiguredEndpointSpec(
            config_key=config_key,
            default_base_url=default_base_url,
            tool_name="weather",
            capability="weather provider access",
            config_prefix=_CONFIG_PREFIX,
            local_policy_source=source,
            network_blocked_message="Weather provider network policy blocked access.",
        ),
    )


async def _fetch_json(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
    extensions: dict[str, str] | None,
    timeout_sec: float,
    max_response_bytes: int,
) -> JSONDict:
    try:
        body, status_code, _ = await read_provider_response_bytes(
            utility_tools,
            url=url,
            extensions=extensions,
            timeout_sec=timeout_sec,
            max_response_bytes=max_response_bytes,
            exceeded_size_message="Weather provider response exceeded size limit.",
        )
        if status_code < 200 or status_code >= 300:
            raise MCPToolError(-32603, _build_provider_status_error(status_code))
    except httpx2.HTTPError as exception:
        raise map_provider_http_exception(
            exception,
            timeout_message="Weather provider timed out while processing the request.",
            request_failed_message="Weather provider request failed.",
        ) from exception
    return parse_provider_json_dict(
        body,
        field="weather provider response",
        invalid_message="Weather provider returned invalid JSON.",
    )


async def tool_weather(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    require_allowed_keys(arguments, allowed_keys=_ALLOWED_ARGUMENT_KEYS, tool_name="weather")
    if not bool(utility_tools.config.get_bool("TOOLS.MCP.WEATHER.ENABLED")):
        raise MCPToolError(
            -32603,
            "weather is disabled by configuration (TOOLS.MCP.WEATHER.ENABLED=false).",
        )
    location = _parse_location(arguments)
    country_code = _parse_country_code(arguments)
    unit_system = require_string_choice(
        arguments.get("units", "metric"),
        key="units",
        choices=("metric", "imperial"),
    )
    forecast_days = _parse_forecast_days(arguments)
    hourly_hours = _parse_hourly_hours(arguments)
    timeout_sec = coerce_lenient_bounded_float(
        utility_tools.config.get("TOOLS.MCP.WEATHER.TIMEOUT_SEC"),
        default=20.0,
        minimum=1.0,
        maximum=120.0,
    )
    max_response_bytes = coerce_lenient_positive_int(
        utility_tools.config.get("TOOLS.MCP.WEATHER.MAX_RESPONSE_BYTES"),
        default=200_000,
        minimum=1,
        maximum=2_000_000,
    )
    geocoding_target = await _resolve_network_target(
        utility_tools,
        config_key="TOOLS.MCP.WEATHER.GEOCODING_BASE_URL",
        default_base_url=_DEFAULT_GEOCODING_BASE_URL,
        source="MCP weather local geocoding provider",
    )
    forecast_target = await _resolve_network_target(
        utility_tools,
        config_key="TOOLS.MCP.WEATHER.FORECAST_BASE_URL",
        default_base_url=_DEFAULT_FORECAST_BASE_URL,
        source="MCP weather local forecast provider",
    )
    start_monotonic = time.monotonic()
    geocoding_payload = await _fetch_json(
        utility_tools,
        url=build_weather_geocoding_url(geocoding_target.base_url, location, country_code),
        extensions=geocoding_target.extensions,
        timeout_sec=timeout_sec,
        max_response_bytes=max_response_bytes,
    )
    geocoded_location = resolve_geocoding_match(geocoding_payload)
    forecast_payload = await _fetch_json(
        utility_tools,
        url=build_weather_forecast_url(
            forecast_target.base_url,
            geocoded_location,
            unit_system,
            forecast_days=forecast_days,
            hourly_hours=hourly_hours,
        ),
        extensions=forecast_target.extensions,
        timeout_sec=timeout_sec,
        max_response_bytes=max_response_bytes,
    )
    elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
    return build_weather_result_payload(
        location=geocoded_location,
        forecast=forecast_payload,
        unit_system=unit_system,
        elapsed_ms=elapsed_ms,
        forecast_days=forecast_days,
        hourly_hours=hourly_hours,
    )
