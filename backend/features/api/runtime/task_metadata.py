"""SoAI - Canonical task metadata builders for API runtime tasks [backend/features/api/runtime/task_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.runtime.protocols import RequestContextProtocol, RequestProtocol
from core.system_api.request_paths import (
    get_scope_path,
    is_public_inference_api_request_path,
)
from features.api.runtime.metadata_values import safe_metadata_value
from features.api.runtime.openai_request_state import (
    extract_openai_api_key_quota_metadata,
)

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_agent_inference_metadata",
    "apply_openai_prompt_token_count_metadata",
    "build_command_task_metadata",
    "build_inference_task_metadata",
)


def _sanitize_quota_reservation(quota: JSONDict) -> JSONDict:
    sanitized: JSONDict = {}
    for key, value in quota.items():
        if key == "key_id":
            sanitized[key] = "[REDACTED]"
            continue
        sanitized[key] = value
    return sanitized


def _extract_openai_api_key_metadata(
    request: RequestProtocol,
    *,
    path: str,
) -> tuple[str | None, JSONDict | None]:
    if not is_public_inference_api_request_path(path):
        return (None, None)
    state = extract_openai_api_key_quota_metadata(request)
    return (state.key_id, state.reservation)


def build_inference_task_metadata(
    context: RequestContextProtocol,
    request: RequestProtocol,
    model: str | None,
    event_type: str,
    endpoint_family: str | None = None,
) -> JSONDict:
    trace_id_value = context.trace_id
    trace_id = (
        trace_id_value if isinstance(trace_id_value, str) and trace_id_value.strip() else None
    )
    path = get_scope_path(request.scope)
    task_metadata: JSONDict = {
        "trace_id": trace_id,
        "path": path,
        "model": model,
        "event_type": event_type,
    }
    if endpoint_family is not None:
        task_metadata["endpoint_family"] = endpoint_family
    api_key_id, quota_reservation = _extract_openai_api_key_metadata(request, path=path)
    if api_key_id is not None:
        task_metadata["api_key_id"] = api_key_id
    if quota_reservation is not None:
        task_metadata["quota"] = _sanitize_quota_reservation(quota_reservation)
    return {key: safe_metadata_value(key, value) for key, value in task_metadata.items()}


def apply_openai_prompt_token_count_metadata(
    task_metadata: JSONDict,
    *,
    prompt_count: PromptOccupancy | None,
) -> None:
    if prompt_count is None:
        return
    task_metadata["prompt_tokens"] = prompt_count.prompt_tokens
    task_metadata["prompt_tokens_precision"] = prompt_count.precision
    if prompt_count.capped:
        task_metadata["prompt_tokens_capped"] = True
        reason = prompt_count.capped_reason
        if isinstance(reason, str) and reason:
            task_metadata["prompt_tokens_capped_reason"] = reason


def apply_agent_inference_metadata(
    task_metadata: JSONDict,
    *,
    tool_image_relay_requested: bool,
) -> None:
    if tool_image_relay_requested:
        task_metadata["agent_tool_image_relay_requested"] = True


def build_command_task_metadata(
    request: RequestProtocol,
    command_type: type[Event],
    audit_action: str,
    audit_target: str,
    audit_details: Mapping[str, JSONValue] | None,
    command_fields: Mapping[str, JSONValue],
) -> JSONDict:
    context = request.state.context
    trace_id_value = context.trace_id
    trace_id = (
        trace_id_value if isinstance(trace_id_value, str) and trace_id_value.strip() else None
    )
    path = get_scope_path(request.scope)
    task_metadata: JSONDict = {
        "trace_id": trace_id,
        "path": path,
        "command": (
            command_type.__name__
            if isinstance(command_type.__name__, str) and command_type.__name__.strip()
            else "command"
        ),
        "audit_action": audit_action,
        "audit_target": audit_target,
    }
    if audit_details:
        task_metadata["audit_details"] = {
            str(detail_key): detail_value for detail_key, detail_value in audit_details.items()
        }
    for metadata_key, metadata_value in command_fields.items():
        if metadata_key in ("reply_channel", "context"):
            continue
        task_metadata[str(metadata_key)] = metadata_value
    api_key_id, quota_reservation = _extract_openai_api_key_metadata(request, path=path)
    if api_key_id is not None:
        task_metadata["api_key_id"] = api_key_id
    if quota_reservation is not None:
        task_metadata["quota"] = _sanitize_quota_reservation(quota_reservation)
    return {key: safe_metadata_value(key, value) for key, value in task_metadata.items()}
