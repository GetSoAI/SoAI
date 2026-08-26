"""SoAI - Proxy worker response validation [backend/plugins/worker/proxy_response_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_json_list,
    require_json_object,
)

__all__ = (
    "require_bool_text_tuple",
    "require_discovered_models",
    "require_plugin_worker_bool",
    "require_process_ids",
)


def require_plugin_worker_bool(value: JSONValue, *, label: str) -> bool:
    return require_bool(
        value,
        label=f"Plugin worker {label} response",
        build_error=ValidationError,
        invalid_message=f"Plugin worker {label} response must be a boolean.",
    )


def require_bool_text_tuple(
    value: JSONValue | tuple[JSONValue, ...],
    *,
    label: str,
) -> tuple[bool, str]:
    if (
        isinstance(value, list | tuple)
        and len(value) >= 2
        and isinstance(value[0], bool)
        and isinstance(value[1], str)
    ):
        return (value[0], value[1])
    raise ValidationError(f"Plugin worker {label} response is malformed.")


def require_discovered_models(value: JSONValue) -> dict[str, JSONDict] | None:
    if value is None:
        return None
    model_map = require_json_object(
        value,
        label="Plugin worker model discovery response",
        build_error=ValidationError,
        invalid_message="Plugin worker model discovery response is malformed.",
    )
    discovered: dict[str, JSONDict] = {}
    for key, item in model_map.items():
        discovered[key] = require_json_object(
            item,
            label=f"Plugin worker model discovery response '{key}'",
            build_error=ValidationError,
            invalid_message="Plugin worker model discovery response contains malformed data.",
        )
    return discovered


def require_process_ids(value: JSONValue) -> list[int]:
    values = require_json_list(
        value,
        label="Plugin worker process PID response",
        build_error=ValidationError,
        invalid_message="Plugin worker process PID response is malformed.",
    )
    ids: list[int] = []
    for item in values:
        ids.append(
            require_int(
                item,
                label="Plugin worker process PID response",
                build_error=ValidationError,
                invalid_message="Plugin worker process PID response is malformed.",
            ),
        )
    return ids
