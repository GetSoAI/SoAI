"""SoAI - OpenAI Responses event persistence normalization [backend/core/openai/response_event_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.response_terminal_policy import is_terminal_response_payload
from core.openai.responses_events import (
    build_canonical_response_json,
    build_failed_response_event,
    normalize_response_event_payload,
)
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict

__all__ = ("normalize_responses_event_for_storage",)

_PROVIDER_FAILURE_MESSAGE = "Upstream provider request failed."
_PROVIDER_FAILURE_CODE = "server_error"


def normalize_responses_event_for_storage(
    *,
    payload: JSONDict,
    response_id: str,
    sequence_number: int,
    default_status: str,
    model: str,
    created_at: int,
) -> tuple[JSONDict, JSONDict, str, bool]:
    error_value = payload.get("error")
    if isinstance(error_value, dict):
        normalized = build_failed_response_event(
            response_id=response_id,
            message=_PROVIDER_FAILURE_MESSAGE,
            code=_PROVIDER_FAILURE_CODE,
            model=model,
            created_at=created_at,
        )
        status = "failed"
    else:
        normalized, status = normalize_response_event_payload(
            payload,
            response_id,
            default_status=default_status,
        )
        status = _resolve_storage_status(status, default_status=default_status)
    enriched = dict(normalized)
    enriched["sequence_number"] = sequence_number
    response_json: JSONDict | None = coerce_json_dict(enriched.get("response"))
    if response_json is None:
        response_json = {
            "id": response_id,
            "object": "response",
            "created_at": created_at,
            "status": status,
            "model": model,
            "output": [],
            "error": None,
        }
    response_json = build_canonical_response_json(
        response_json=response_json,
        response_id=response_id,
        status=status,
        model=model,
        created_at=created_at,
    )
    if status == "failed" or isinstance(response_json.get("error"), dict):
        response_json["error"] = {
            "code": _PROVIDER_FAILURE_CODE,
            "message": _PROVIDER_FAILURE_MESSAGE,
        }
    enriched["response"] = dict(response_json)
    return enriched, response_json, status, is_terminal_response_payload(enriched)


def _resolve_storage_status(status: str, *, default_status: str) -> str:
    resolved_status = status.strip() if isinstance(status, str) else ""
    if resolved_status:
        return resolved_status
    default_status_text = default_status.strip() if isinstance(default_status, str) else ""
    return default_status_text or "in_progress"
