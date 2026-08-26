"""SoAI - File manager settings resolution [backend/files/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import is_json_value
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("resolve_file_manager_settings",)


def resolve_file_manager_settings(config: ConfigProtocol) -> tuple[bool, int, float]:
    raw_config = config.get("DATA.FILES", {})
    if not isinstance(raw_config, dict):
        raise ValidationError("DATA.FILES must be a dictionary.")
    config_dict: dict[str, JSONValue] = {}
    for key, value in raw_config.items():
        if not isinstance(key, str):
            raise ValidationError("DATA.FILES keys must be strings.")
        if not is_json_value(value):
            raise ValidationError("DATA.FILES values must be JSON-compatible.")
        config_dict[key] = value

    cleanup_enabled = config_dict.get("INITIAL_CLEANUP_ENABLED", True)
    perform_startup_cleanup = parse_bool(cleanup_enabled, default=True)
    concurrency_value = config_dict.get("RECONCILIATION_CONCURRENCY", 32)
    reconciliation_concurrency = coerce_positive_int(concurrency_value, default=32, minimum=1)
    timeout_value = config_dict.get("DIRECTORY_SCAN_TIMEOUT_SEC", LOCAL_IO_TIMEOUT_SEC)
    directory_scan_timeout_seconds = coerce_positive_float(
        timeout_value,
        default=LOCAL_IO_TIMEOUT_SEC,
        minimum=10.0,
    )
    return (
        bool(perform_startup_cleanup),
        reconciliation_concurrency,
        directory_scan_timeout_seconds,
    )
