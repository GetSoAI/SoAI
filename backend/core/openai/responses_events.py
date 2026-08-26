"""SoAI - OpenAI Responses event payload helpers [backend/core/openai/responses_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.response_terminal_policy import (
    coerce_response_event_type,
    coerce_response_status,
    response_status_from_event,
    response_status_to_event_type,
)
from core.validation.strict_numbers import coerce_optional_positive_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_canonical_response_json",
    "build_failed_response_event",
    "build_failed_response_json",
    "build_response_event_from_json",
    "build_response_status_event",
    "build_response_status_json",
    "coerce_response_created_at",
    "normalize_response_event_payload",
)


def _coerce_response_string_field(value: JSONValue | None, *, default: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text or default


def coerce_response_created_at(value: JSONValue, *, default: int) -> int:
    resolved = coerce_optional_positive_int_strict(value)
    if resolved is not None:
        return resolved
    return int(default)


def build_canonical_response_json(
    *,
    response_json: JSONDict,
    response_id: str,
    status: str,
    model: str,
    created_at: int,
) -> JSONDict:
    canonical_response = dict(response_json)
    canonical_response["id"] = _coerce_response_string_field(
        canonical_response.get("id"),
        default=response_id,
    )
    canonical_response["object"] = _coerce_response_string_field(
        canonical_response.get("object"),
        default="response",
    )
    canonical_response["created_at"] = coerce_response_created_at(
        canonical_response.get("created_at"),
        default=created_at,
    )
    canonical_response["status"] = coerce_response_status(status, default_status="completed")
    canonical_response["model"] = _coerce_response_string_field(
        canonical_response.get("model"),
        default=model,
    )
    output_value = canonical_response.get("output")
    canonical_response["output"] = list(output_value) if isinstance(output_value, list) else []
    error_value = canonical_response.get("error")
    canonical_response["error"] = dict(error_value) if isinstance(error_value, dict) else None
    return canonical_response


def normalize_response_event_payload(
    payload: JSONDict,
    response_id: str,
    *,
    default_status: str = "completed",
) -> tuple[JSONDict, str]:
    normalized: JSONDict = dict(payload)
    event_type = coerce_response_event_type(normalized.get("type"))
    if event_type:
        normalized["type"] = event_type
    response_value = normalized.get("response")
    if not isinstance(response_value, dict):
        status = response_status_from_event(normalized, default_status=default_status)
        return normalized, status

    response_payload = dict(response_value)
    response_payload["id"] = response_id
    status = response_status_from_event(normalized, default_status=default_status)
    response_payload["status"] = status
    normalized["response"] = response_payload
    return normalized, status


def build_response_event_from_json(
    *,
    response_json: JSONDict,
    default_status: str = "completed",
) -> JSONDict:
    response = dict(response_json)
    status = response_status_from_event({"response": response}, default_status=default_status)
    return {"type": response_status_to_event_type(status), "response": response}


def build_failed_response_event(
    *,
    response_id: str,
    message: str,
    code: str,
    model: str,
    created_at: int,
) -> JSONDict:
    return {
        "type": "response.failed",
        "response": build_failed_response_json(
            response_id=response_id,
            message=message,
            code=code,
            model=model,
            created_at=created_at,
        ),
    }


def build_failed_response_json(
    *,
    response_id: str,
    message: str,
    code: str,
    model: str,
    created_at: int,
) -> JSONDict:
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(created_at),
        "status": "failed",
        "model": model,
        "output": [],
        "error": {
            "code": code,
            "message": message,
        },
    }


def build_response_status_event(
    *,
    response_id: str,
    status: str,
    model: str,
    created_at: int,
) -> JSONDict:
    return {
        "type": response_status_to_event_type(status),
        "response": build_response_status_json(
            response_id=response_id,
            status=status,
            model=model,
            created_at=created_at,
        ),
    }


def build_response_status_json(
    *,
    response_id: str,
    status: str,
    model: str,
    created_at: int,
) -> JSONDict:
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(created_at),
        "status": status,
        "model": model,
        "output": [],
        "error": None,
    }
