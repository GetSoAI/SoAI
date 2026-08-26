"""SoAI - Assistant timeline canonical tool payload state [backend/features/assistant_timeline/tool_payload_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "build_latest_tool_update_payload",
    "record_latest_tool_payload_locked",
    "resolve_latest_tool_payload",
)


def _copy_payload(payload: JSONDict) -> JSONDict:
    return dict(payload)


def record_latest_tool_payload_locked(runtime: AssistantTimelineRuntime, payload: JSONDict) -> None:
    call_id_value = payload.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        return
    runtime.latest_tool_payload_by_call_id[call_id] = _copy_payload(payload)


def resolve_latest_tool_payload(runtime: AssistantTimelineRuntime, call_id: str) -> JSONDict | None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        return None
    payload = runtime.latest_tool_payload_by_call_id.get(normalized_call_id)
    if payload is None:
        return None
    return _copy_payload(payload)


def build_latest_tool_update_payload(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    result: JSONValue,
) -> JSONDict | None:
    payload = resolve_latest_tool_payload(runtime, call_id)
    if payload is None:
        return None
    payload["result"] = result
    return payload
