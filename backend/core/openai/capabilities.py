"""SoAI - OpenAI capabilities normalization for persisted/configured values [backend/core/openai/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.protocols import StandardLogger
from core.serialization.json_parsing import parse_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("normalize_openai_capabilities",)


def normalize_openai_capabilities(
    value: JSONValue,
    *,
    logger_instance: StandardLogger | None = None,
) -> JSONDict:
    if isinstance(value, str):
        raw_value = value
        try:
            value = parse_json_value(raw_value)
        except (ValidationError, TypeError):
            if logger_instance:
                logger_instance.warning(
                    "Failed to parse openai_capabilities as JSON: %s",
                    raw_value[:100] if len(raw_value) > 100 else raw_value,
                )
            return {}
    if not isinstance(value, dict):
        return {}

    def _normalize_value(payload: JSONValue) -> JSONValue:
        if isinstance(payload, dict):
            return {
                str(payload_key): _normalize_value(payload_value)
                for payload_key, payload_value in payload.items()
            }
        if isinstance(payload, list):
            return [_normalize_value(item) for item in payload]
        if isinstance(payload, str | bool):
            return payload
        if isinstance(payload, int | float):
            return payload
        if payload in (None, ""):
            return False
        return str(payload)

    return {str(key): _normalize_value(entry) for key, entry in value.items()}
