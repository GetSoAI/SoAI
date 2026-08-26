"""SoAI - OpenAI Responses terminal status policy [backend/core/openai/response_terminal_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_response_event_type",
    "coerce_response_status",
    "is_terminal_response_payload",
    "is_terminal_response_status",
    "is_successful_response_status",
    "response_status_from_event",
    "response_status_to_event_type",
)

TERMINAL_RESPONSE_STATUSES: tuple[str, ...] = (
    "completed",
    "failed",
    "incomplete",
    "cancelled",
)
SUCCESSFUL_RESPONSE_STATUSES: tuple[str, ...] = ("completed", "incomplete")

KNOWN_NONTERMINAL_RESPONSE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "response.output_item.added",
        "response.output_item.done",
        "response.output_text.delta",
        "response.function_call_arguments.delta",
        "response.reasoning_summary_text.delta",
        "response.reasoning_text.delta",
        "response.reasoning_summary_part.added",
    },
)


def coerce_response_status(value: JSONValue | None, *, default_status: str) -> str:
    if not isinstance(value, str):
        return default_status
    status = value.strip().lower()
    return status or default_status


def coerce_response_event_type(value: JSONValue | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def response_status_to_event_type(value: str) -> str:
    normalized_status = coerce_response_status(value, default_status="completed")
    match normalized_status:
        case "queued":
            return "response.queued"
        case "cancelling":
            return "response.cancelling"
        case "completed":
            return "response.completed"
        case "failed":
            return "response.failed"
        case "in_progress":
            return "response.in_progress"
        case "incomplete":
            return "response.incomplete"
        case "cancelled":
            return "response.cancelled"
        case _:
            return f"response.{normalized_status}"


def _response_event_to_status(event_type: str, *, default_status: str) -> str:
    match event_type:
        case "response.created":
            return "in_progress"
        case "response.in_progress":
            return "in_progress"
        case "response.queued":
            return "queued"
        case "response.completed":
            return "completed"
        case "response.failed":
            return "failed"
        case "response.incomplete":
            return "incomplete"
        case "response.cancelling":
            return "cancelling"
        case "response.cancelled":
            return "cancelled"
        case _:
            return default_status


def response_status_from_event(payload: JSONDict, *, default_status: str = "") -> str:
    response_value = payload.get("response")
    event_type = coerce_response_event_type(payload.get("type"))
    if isinstance(response_value, dict):
        status = coerce_response_status(response_value.get("status"), default_status="")
        if status:
            return status
        inferred_status = _response_event_to_status(event_type, default_status="")
        return inferred_status or default_status
    inferred_status = _response_event_to_status(event_type, default_status="")
    if inferred_status:
        return inferred_status
    if event_type in KNOWN_NONTERMINAL_RESPONSE_EVENT_TYPES or event_type.startswith("response."):
        return ""
    return default_status


def is_terminal_response_status(status: str) -> bool:
    return coerce_response_status(status, default_status="") in TERMINAL_RESPONSE_STATUSES


def is_successful_response_status(status: str) -> bool:
    return coerce_response_status(status, default_status="") in SUCCESSFUL_RESPONSE_STATUSES


def is_terminal_response_payload(payload: JSONDict) -> bool:
    return is_terminal_response_status(response_status_from_event(payload))
