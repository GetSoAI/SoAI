"""SoAI - OpenAI request state helpers [backend/features/api/runtime/openai_request_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from core.openai.request_pipeline import (
    apply_openai_stored_chat_completion_model_override,
)
from core.runtime.protocols import RequestProtocol
from core.types.json import is_json_dict
from core.types.json_value import copy_json_dict
from features.api.runtime.context import get_request_trace_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OpenAIAPIKeyContext",
    "OpenAIRequestQuotaState",
    "apply_openai_api_key_quota_state",
    "apply_stored_chat_completion_model_override",
    "clear_openai_api_key_quota_reservation",
    "extract_openai_api_key_quota_metadata",
    "initialize_openai_request_state",
    "read_stored_chat_completion_request_json",
    "record_stored_chat_completion_request_json",
    "resolve_openai_api_key_context_optional",
    "resolve_openai_api_key_id_optional",
    "resolve_request_trace_id_optional",
)


@dataclass(frozen=True, slots=True)
class OpenAIAPIKeyContext:
    key_id: str
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class OpenAIRequestQuotaState:
    key_id: str | None
    reservation: JSONDict | None


def initialize_openai_request_state(request: Request) -> None:
    request.state.openai_api_key_id = None
    request.state.openai_api_key_quota_reservation = None
    request.state.openai_stored_chat_completion_request_json = None


def resolve_request_trace_id_optional(request: RequestProtocol) -> str | None:
    try:
        context = request.state.context
    except AttributeError:
        return None
    try:
        trace_id = context.trace_id
    except AttributeError:
        return None
    if not isinstance(trace_id, str):
        return None
    normalized = trace_id.strip()
    return normalized or None


def resolve_openai_api_key_id_optional(request: RequestProtocol) -> str | None:
    try:
        state = request.state
    except AttributeError:
        return None
    try:
        api_key_id_value = state.openai_api_key_id
    except AttributeError:
        api_key_id_value = None
    if isinstance(api_key_id_value, str):
        api_key_id = api_key_id_value.strip()
        if api_key_id:
            return api_key_id
    try:
        auth_method = state.auth_method
    except AttributeError:
        auth_method = None
    if auth_method != "openai_api_key":
        return None
    try:
        token_payload = state.token_payload
    except AttributeError:
        token_payload = None
    if not is_json_dict(token_payload):
        return None
    key_id_value = token_payload.get("key_id")
    if not isinstance(key_id_value, str):
        return None
    key_id = key_id_value.strip()
    return key_id or None


def resolve_openai_api_key_context_optional(
    request: RequestProtocol,
) -> OpenAIAPIKeyContext | None:
    key_id = resolve_openai_api_key_id_optional(request)
    if key_id is None:
        return None
    return OpenAIAPIKeyContext(
        key_id=key_id,
        trace_id=get_request_trace_id(request),
    )


def apply_openai_api_key_quota_state(
    request: RequestProtocol,
    *,
    key_id: str | None,
    reservation: JSONDict | None,
) -> None:
    if key_id is not None:
        request.state.openai_api_key_id = key_id
    if reservation is not None:
        request.state.openai_api_key_quota_reservation = reservation


def clear_openai_api_key_quota_reservation(request: RequestProtocol) -> None:
    request.state.openai_api_key_quota_reservation = None


def record_stored_chat_completion_request_json(
    request: RequestProtocol,
    request_json: JSONDict,
) -> None:
    request.state.openai_stored_chat_completion_request_json = copy_json_dict(request_json)


def read_stored_chat_completion_request_json(request: RequestProtocol) -> JSONDict | None:
    try:
        stored_request_json_value = request.state.openai_stored_chat_completion_request_json
    except AttributeError:
        return None
    if not is_json_dict(stored_request_json_value):
        return None
    return copy_json_dict(stored_request_json_value)


def apply_stored_chat_completion_model_override(
    request: RequestProtocol,
    *,
    override_model_id: str,
) -> None:
    stored_request_json = read_stored_chat_completion_request_json(request)
    if stored_request_json is None:
        return
    request.state.openai_stored_chat_completion_request_json = (
        apply_openai_stored_chat_completion_model_override(
            stored_request_json,
            override_model_id=override_model_id,
        )
    )


def extract_openai_api_key_quota_metadata(request: RequestProtocol) -> OpenAIRequestQuotaState:
    api_key_id = resolve_openai_api_key_id_optional(request)
    try:
        quota_value = request.state.openai_api_key_quota_reservation
    except AttributeError:
        quota_value = None
    quota_reservation = quota_value if is_json_dict(quota_value) else None
    if api_key_id is None and quota_reservation is not None:
        quota_key_id_value = quota_reservation.get("key_id")
        api_key_id = (
            quota_key_id_value.strip()
            if isinstance(quota_key_id_value, str) and quota_key_id_value.strip()
            else None
        )
    return OpenAIRequestQuotaState(key_id=api_key_id, reservation=quota_reservation)
