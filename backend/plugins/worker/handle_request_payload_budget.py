"""SoAI - Plugin worker handle_request IPC payload budgeting [backend/plugins/worker/handle_request_payload_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import PayloadTooLargeError
from core.ipc.message_encoding import encode_ipc_message_bytes
from core.ipc.multiplexed_requests import build_ipc_request_message
from core.tool_calls.tool_result_omission import build_tool_result_omission_stub_json
from core.types.json import JSONDict
from core.types.json_value import copy_json_dict, copy_json_dict_list

__all__ = ("fit_handle_request_payload_to_ipc_budget",)


def _resolve_tool_names_by_call_id(messages: list[JSONDict]) -> dict[str, str]:
    tool_names_by_call_id: dict[str, str] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        tool_calls_value = message.get("tool_calls")
        if not isinstance(tool_calls_value, list):
            continue
        for tool_call_value in tool_calls_value:
            if not isinstance(tool_call_value, dict):
                continue
            call_id_value = tool_call_value.get("id")
            call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            if not call_id:
                continue
            function_value = tool_call_value.get("function")
            if not isinstance(function_value, dict):
                continue
            name_value = function_value.get("name")
            tool_name = name_value.strip() if isinstance(name_value, str) else ""
            if tool_name:
                tool_names_by_call_id[call_id] = tool_name
    return tool_names_by_call_id


def _build_request_message(
    *,
    request_id: str,
    payload: JSONDict,
) -> JSONDict:
    return build_ipc_request_message(
        method="call.handle_request",
        request_id=request_id,
        payload=payload,
    )


def _assert_fits_budget(*, request_id: str, payload: JSONDict, max_bytes: int) -> None:
    request_message = _build_request_message(request_id=request_id, payload=payload)
    encode_ipc_message_bytes(
        request_message,
        max_bytes=max_bytes,
        details={"method": "call.handle_request", "request_id": request_id},
        operation="plugins.worker.handle_request_payload_budget.measure",
    )


def _replace_tool_message_with_omission_stub(
    *,
    messages: list[JSONDict],
    message_index: int,
    tool_names_by_call_id: dict[str, str],
) -> None:
    message = messages[message_index]
    call_id_value = message.get("tool_call_id")
    tool_call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    message["content"] = build_tool_result_omission_stub_json(
        tool_call_id=tool_call_id,
        tool_name=tool_names_by_call_id.get(tool_call_id, "unknown"),
    )
    message.pop("tool_call_projections", None)


def _resolve_tool_message_indexes(messages: list[JSONDict]) -> list[int]:
    tool_indexes: list[int] = []
    for message_index, message in enumerate(messages):
        if message.get("role") != "tool":
            continue
        tool_indexes.append(message_index)
    return tool_indexes


def fit_handle_request_payload_to_ipc_budget(
    *,
    request_id: str,
    payload: JSONDict,
    max_bytes: int,
) -> JSONDict:
    candidate_payload = copy_json_dict(payload)
    try:
        _assert_fits_budget(
            request_id=request_id,
            payload=candidate_payload,
            max_bytes=max_bytes,
        )
        return candidate_payload
    except PayloadTooLargeError as exception:
        initial_oversize_error = exception
    request_json_value = candidate_payload.get("request_json")
    if not isinstance(request_json_value, dict):
        raise initial_oversize_error
    messages_value = request_json_value.get("messages")
    if not isinstance(messages_value, list):
        raise initial_oversize_error
    messages: list[JSONDict] = []
    for message_value in messages_value:
        if not isinstance(message_value, dict):
            raise initial_oversize_error
        messages.append(dict(message_value))
    compacted_messages = copy_json_dict_list(messages)
    tool_names_by_call_id = _resolve_tool_names_by_call_id(compacted_messages)
    latest_oversize_error = initial_oversize_error
    for message_index in _resolve_tool_message_indexes(compacted_messages):
        _replace_tool_message_with_omission_stub(
            messages=compacted_messages,
            message_index=message_index,
            tool_names_by_call_id=tool_names_by_call_id,
        )
        compacted_request_json = dict(request_json_value)
        compacted_request_json["messages"] = compacted_messages
        candidate_payload["request_json"] = compacted_request_json
        try:
            _assert_fits_budget(
                request_id=request_id,
                payload=candidate_payload,
                max_bytes=max_bytes,
            )
            return candidate_payload
        except PayloadTooLargeError as exception:
            latest_oversize_error = exception
    raise latest_oversize_error
