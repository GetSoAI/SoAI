"""SoAI - Startup HTTP client routing config extraction helpers [backend/app/runtime_http_client_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import is_json_value
from core.types.json_value import filter_json_mapping

if TYPE_CHECKING:
    from core.config.runtime_config import Config
    from core.types.json import JSONValue

__all__ = (
    "extract_startup_http_client_section",
    "normalize_http_client_section",
)


def normalize_http_client_section(raw_value: JSONValue) -> dict[str, JSONValue] | None:
    if not isinstance(raw_value, dict):
        return None
    return filter_json_mapping(raw_value)


def extract_startup_http_client_section(
    configuration: Config | None,
    config_key: str,
) -> dict[str, JSONValue] | None:
    if configuration is None:
        return None
    raw_value = configuration.get(config_key)
    if not is_json_value(raw_value):
        return None
    return normalize_http_client_section(raw_value)
