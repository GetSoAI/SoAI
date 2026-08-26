"""SoAI - MCP argument presence normalization helpers [backend/core/mcp/argument_presence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict, JSONValue

__all__ = (
    "argument_is_blank_placeholder",
    "argument_is_effectively_provided",
    "argument_is_zero_number_placeholder",
    "get_effective_optional_argument",
    "key_is_effectively_provided",
)


def argument_is_blank_placeholder(value: JSONValue) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def argument_is_zero_number_placeholder(value: JSONValue) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return value == 0


def argument_is_effectively_provided(value: JSONValue) -> bool:
    return not argument_is_blank_placeholder(value)


def key_is_effectively_provided(arguments: JSONDict, key: str) -> bool:
    if key not in arguments:
        return False
    return argument_is_effectively_provided(arguments[key])


def get_effective_optional_argument(arguments: JSONDict, key: str) -> JSONValue | None:
    if not key_is_effectively_provided(arguments, key):
        return None
    return arguments[key]
