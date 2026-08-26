"""SoAI - Agent shell stop WebUI route registration [backend/features/api/routes/webui/conversation_agent_shell_stop_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import Depends, Request

from core.execution.owned_execution_tasks import request_owned_execution_cancellation
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
    TOOL_CALL_STATUS_RUNNING,
    is_terminal_tool_call_status,
    normalize_tool_call_status,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_not_found
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.agent_state import AgentShellToolStopResponse
from features.api.schemas.conversations import AgentShellToolStopRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_shell_stop_route",)

SHELL_TOOL_NAME = "shell"
SHELL_OWNER_TYPE = "conversation"


def _read_tool_call_text(tool_call: JSONDict, field_name: str) -> str | None:
    value = tool_call.get(field_name)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _resolve_terminal_status(status: str) -> Literal["completed", "cancelled", "error"] | None:
    normalized_status = normalize_tool_call_status(status)
    if normalized_status == TOOL_CALL_STATUS_COMPLETED:
        return "completed"
    if normalized_status == TOOL_CALL_STATUS_CANCELLED:
        return "cancelled"
    if normalized_status == TOOL_CALL_STATUS_ERROR:
        return "error"
    return None


def _metadata_text(metadata: JSONDict, key: str) -> str:
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) else ""


async def _reload_terminal_response(
    *,
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    payload: AgentShellToolStopRequest,
) -> AgentShellToolStopResponse:
    tool_call = (
        await api_context.dependencies.database_tool_calls.get_tool_call_for_assistant_variant(
            conv_id=conv_id,
            call_id=payload.tool_call_id,
            assistant_turn_at_ms=payload.assistant_turn_at_ms,
            model_variant_index=payload.model_variant_index,
        )
    )
    if tool_call is None:
        raise_not_found(request, "Shell tool call not found.")
    status_value = _read_tool_call_text(tool_call, "status")
    if status_value is None:
        raise_conflict(request, "Shell tool call status is invalid.")
    status = normalize_tool_call_status(status_value)
    if not is_terminal_tool_call_status(status):
        raise_conflict(request, "Shell owner task is already terminal.")
    return AgentShellToolStopResponse(
        conv_id=conv_id,
        tool_call_id=payload.tool_call_id,
        status="already_terminal",
        terminal_status=_resolve_terminal_status(status),
        owner_task_id=None,
    )


def register_shell_stop_route(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/agent/tools/shell/stop",
        response_model=AgentShellToolStopResponse,
    )
    async def stop_shell_tool_call(
        request: Request,
        conv_id: str,
        payload: AgentShellToolStopRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> AgentShellToolStopResponse:
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        resolved_conv_id = conversation_context.resolved_conv_id
        tool_call = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_tool_calls.get_tool_call_for_assistant_variant(
                conv_id=resolved_conv_id,
                call_id=payload.tool_call_id,
                assistant_turn_at_ms=payload.assistant_turn_at_ms,
                model_variant_index=payload.model_variant_index,
            ),
            message="Shell tool call not found.",
        )
        if _read_tool_call_text(tool_call, "conv_id") != resolved_conv_id:
            raise_not_found(request, "Shell tool call not found.")
        if _read_tool_call_text(tool_call, "tool_name") != SHELL_TOOL_NAME:
            raise_conflict(request, "Tool call is not a shell call.")
        status_value = _read_tool_call_text(tool_call, "status")
        if status_value is None:
            raise_conflict(request, "Shell tool call status is invalid.")
        status = normalize_tool_call_status(status_value)
        if is_terminal_tool_call_status(status):
            return AgentShellToolStopResponse(
                conv_id=resolved_conv_id,
                tool_call_id=payload.tool_call_id,
                status="already_terminal",
                terminal_status=_resolve_terminal_status(status),
                owner_task_id=None,
            )
        if status != TOOL_CALL_STATUS_RUNNING:
            raise_conflict(request, "Shell is not running.")
        owner_task_id = _read_tool_call_text(tool_call, "owner_task_id")
        if owner_task_id is None:
            raise_conflict(request, "Running shell has no cancellable owner task.")
        task = await api_context.dependencies.task_registry.get(owner_task_id, force_refresh=True)
        if task is None:
            raise_conflict(request, "Shell owner task was not found.")
        if task.task_type != TASK_TYPE_BACKGROUND_JOB:
            raise_conflict(request, "Shell owner task has an invalid task type.")
        if task.user_id != current_user["id"]:
            raise_conflict(request, "Shell owner task does not match the user.")
        if task.owner_type != SHELL_OWNER_TYPE or task.owner_id != resolved_conv_id:
            raise_conflict(request, "Shell owner task does not match the conversation.")
        if task.status.is_terminal():
            return await _reload_terminal_response(
                request=request,
                api_context=api_context,
                conv_id=resolved_conv_id,
                payload=payload,
            )
        metadata = dict(task.metadata)
        if _metadata_text(metadata, "tool_name") != SHELL_TOOL_NAME:
            raise_conflict(request, "Shell owner task metadata does not match the tool.")
        if _metadata_text(metadata, "conv_id") != resolved_conv_id:
            raise_conflict(
                request,
                "Shell owner task metadata does not match the conversation.",
            )
        if _metadata_text(metadata, "call_id") != payload.tool_call_id:
            raise_conflict(
                request,
                "Shell owner task metadata does not match the tool call.",
            )
        cancelled_task = await request_owned_execution_cancellation(
            api_context.dependencies.task_registry,
            owner_task_id=owner_task_id,
            reason="Shell stop requested from WebUI.",
        )
        if cancelled_task is None:
            raise_conflict(request, "Shell owner task was not found.")
        if cancelled_task.status.is_terminal():
            return await _reload_terminal_response(
                request=request,
                api_context=api_context,
                conv_id=resolved_conv_id,
                payload=payload,
            )
        return AgentShellToolStopResponse(
            conv_id=resolved_conv_id,
            tool_call_id=payload.tool_call_id,
            status="cancellation_requested",
            terminal_status=None,
            owner_task_id=owner_task_id,
        )
