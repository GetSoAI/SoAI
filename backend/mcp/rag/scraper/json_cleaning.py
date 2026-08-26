"""SoAI - JSON API response noise key stripping [backend/mcp/rag/scraper/json_cleaning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONValue

__all__ = ("strip_json_noise_keys",)

_NOISE_KEY_EXACT: frozenset[str] = frozenset(
    {
        "__typename",
        "_links",
        "ads",
        "advertising",
        "analytics",
        "copyright",
        "debug",
        "request_id",
        "telemetry",
        "trace_id",
        "tracking",
    },
)

_NOISE_KEY_CONTAINS: tuple[str, ...] = (
    "advertising",
    "analytics",
    "telemetry",
    "tracking",
)


def _is_noise_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _NOISE_KEY_EXACT:
        return True
    return any(pattern in lowered for pattern in _NOISE_KEY_CONTAINS)


def _clean_value(value: JSONValue) -> JSONValue:
    if isinstance(value, dict):
        return {
            key: _clean_value(item_value)
            for key, item_value in value.items()
            if not _is_noise_key(key)
        }
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    return value


def strip_json_noise_keys(data: JSONValue) -> JSONValue:
    return _clean_value(data)
