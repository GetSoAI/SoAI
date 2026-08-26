"""SoAI - Proxy plugin response payload helpers [backend/plugins/worker/proxy_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_object, require_json_object_list

__all__ = (
    "json_dict_list",
    "payload_from_message",
    "require_json_response_value",
)


def payload_from_message(message: JSONDict) -> JSONDict:
    return require_json_object(
        message.get("payload"),
        label="Plugin worker IPC message payload",
        build_error=ValidationError,
        invalid_message="Plugin worker IPC message payload must be a JSON object.",
    )


def require_json_response_value(payload: JSONDict, *, method: str) -> JSONDict:
    return require_json_object(
        payload.get("value"),
        label=f"Plugin worker method '{method}' response",
        build_error=ValidationError,
        invalid_message=f"Plugin worker method '{method}' did not return a JSON object.",
    )


def json_dict_list(value: JSONValue | JSONDict) -> list[JSONDict]:
    return require_json_object_list(
        value,
        label="Plugin worker response value",
        build_error=ValidationError,
        invalid_message="Plugin worker response value must be a JSON object list.",
        entry_message="Plugin worker response list must contain only JSON objects.",
    )
