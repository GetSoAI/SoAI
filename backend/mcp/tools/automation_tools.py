"""SoAI - MCP utility tools: automation_* [backend/mcp/tools/automation_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_TERMINAL_RUN_STATUSES
from core.automation.automation_definition_updates import update_automation_definition
from core.automation.automation_model_reference import (
    build_automation_model_validation_payload,
    should_validate_automation_update_model_reference,
    validate_automation_payload_model_reference,
)
from core.automation.automation_run_serialization import (
    serialize_automation_run_snapshot,
)
from core.automation.automation_run_task_lifecycle import (
    ensure_automation_run_owner_task_attached,
    read_automation_run_owner_task_id,
)
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.errors.exceptions import SoAITimeoutError
from core.tasks.owned_task_wait import wait_for_owned_task_snapshot
from core.timing.durations import minutes_to_ms
from core.timing.epoch import epoch_ms
from mcp.tools.argument_fields import (
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.automation_arguments import (
    allowed_automation_create_keys,
    allowed_automation_get_run_keys,
    allowed_automation_run_now_keys,
    allowed_automation_update_keys,
    allowed_automation_wait_run_keys,
)
from mcp.tools.automation_workspace import normalize_automation_payload_workspace
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.timeout_ms import resolve_timeout_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "tool_automation_create",
    "tool_automation_run_enqueue",
    "tool_automation_run_get",
    "tool_automation_run_wait",
    "tool_automation_update",
)


def _is_terminal_run(run: JSONDict) -> bool:
    status = run.get("status")
    if isinstance(status, str) and status in AUTOMATION_TERMINAL_RUN_STATUSES:
        return True
    finished_at_ms = run.get("finished_at_ms")
    if (
        isinstance(finished_at_ms, int)
        and not isinstance(finished_at_ms, bool)
        and finished_at_ms > 0
    ):
        return True
    return False


async def _validate_automation_payload_model(
    utility_tools: MCPUtilityToolsProtocol,
    payload: JSONDict,
) -> None:
    await validate_automation_payload_model_reference(
        payload,
        now_ms=epoch_ms(),
        disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
            utility_tools.config,
        ),
        model_resolution_service=utility_tools.model_resolution_service,
        model_information_service=utility_tools.model_information_service,
        model_virtual_model_service=utility_tools.model_virtual_model_service,
    )


async def _load_automation_or_raise(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    automation_id: str,
    user_id: int,
) -> JSONDict:
    automation = await utility_tools.database_automations.get_automation(
        automation_id,
        user_id,
    )
    if not isinstance(automation, dict):
        raise MCPToolError(-32602, "Automation not found.")
    return automation


async def tool_automation_create(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, allowed_automation_create_keys())
    user_id = require_authenticated_user_id(utility_tools, tool_name="automation_create")
    payload: JSONDict = dict(arguments)
    payload = await normalize_automation_payload_workspace(
        utility_tools,
        payload=payload,
        user_id=user_id,
    )
    await _validate_automation_payload_model(utility_tools, payload)
    automation = await utility_tools.database_automations.create_automation(user_id, payload)
    if not isinstance(automation, dict):
        raise MCPToolError(-32603, "automation_create returned an invalid automation payload.")
    return {"automation": automation}


async def tool_automation_update(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, allowed_automation_update_keys())
    user_id = require_authenticated_user_id(utility_tools, tool_name="automation_update")
    automation_id = require_non_empty_string(
        get_arg(arguments, "automation_id"),
        key="automation_id",
    )
    payload: JSONDict = {
        key: value
        for key, value in arguments.items()
        if isinstance(key, str) and key != "automation_id"
    }
    payload = await normalize_automation_payload_workspace(
        utility_tools,
        payload=payload,
        user_id=user_id,
    )
    if should_validate_automation_update_model_reference(payload):
        current_record = await _load_automation_or_raise(
            utility_tools,
            automation_id=automation_id,
            user_id=user_id,
        )
        validation_payload = build_automation_model_validation_payload(current_record, payload)
        await _validate_automation_payload_model(utility_tools, validation_payload)
    result = await update_automation_definition(
        utility_tools.database_automations,
        utility_tools.task_registry,
        automation_id=automation_id,
        user_id=user_id,
        payload=payload,
        event_bus=utility_tools.event_bus,
        database_chat_identity_defaults=utility_tools.database_chat_identity_defaults,
        database_chat_model_defaults=utility_tools.database_chat_model_defaults,
    )
    if result.automation is None:
        raise MCPToolError(-32602, "Automation not found.")
    if not isinstance(result.automation, dict):
        raise MCPToolError(-32603, "automation_update returned an invalid automation payload.")
    return {"automation": result.automation}


async def tool_automation_run_enqueue(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, allowed_automation_run_now_keys())
    user_id = require_authenticated_user_id(utility_tools, tool_name="automation_run_enqueue")
    automation_id = require_non_empty_string(
        get_arg(arguments, "automation_id"),
        key="automation_id",
    )
    automation = await _load_automation_or_raise(
        utility_tools,
        automation_id=automation_id,
        user_id=user_id,
    )
    validation_payload = build_automation_model_validation_payload(automation, {})
    await _validate_automation_payload_model(utility_tools, validation_payload)
    run_record = await utility_tools.database_automation_runs.create_run_now(
        automation_id,
        user_id,
        epoch_ms(),
    )
    run_record = await ensure_automation_run_owner_task_attached(
        utility_tools.database_automation_runs,
        utility_tools.task_registry,
        run_record=run_record,
    )
    serialized_run_record = serialize_automation_run_snapshot(run_record)
    if serialized_run_record is None:
        raise MCPToolError(-32603, "automation_run_enqueue returned an invalid run payload.")
    return {"run": serialized_run_record}


async def tool_automation_run_get(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, allowed_automation_get_run_keys())
    user_id = require_authenticated_user_id(utility_tools, tool_name="automation_run_get")
    run_id = require_non_empty_string(get_arg(arguments, "run_id"), key="run_id")
    serialized_run_record = await _load_automation_run_snapshot(
        utility_tools,
        run_id=run_id,
        user_id=user_id,
        error_tool_name="automation_run_get",
    )
    return {"run": serialized_run_record}


async def _load_automation_run_snapshot(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    run_id: str,
    user_id: int,
    error_tool_name: str,
) -> JSONDict | None:
    run_record = await utility_tools.database_automation_runs.get_run(run_id, user_id)
    serialized_run_record = serialize_automation_run_snapshot(run_record)
    if run_record is not None and serialized_run_record is None:
        raise MCPToolError(-32603, f"{error_tool_name} returned an invalid run payload.")
    return serialized_run_record


async def tool_automation_run_wait(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, allowed_automation_wait_run_keys())
    user_id = require_authenticated_user_id(utility_tools, tool_name="automation_run_wait")
    run_id = require_non_empty_string(get_arg(arguments, "run_id"), key="run_id")
    timeout_ms = resolve_timeout_ms(
        arguments,
        field_name="timeout_ms",
        config=utility_tools.config,
        config_key="TOOLS.MCP.AUTOMATION.RUN_WAIT_TIMEOUT_MS",
        default_timeout_ms=minutes_to_ms(1),
    )
    run_record = await _load_automation_run_snapshot(
        utility_tools,
        run_id=run_id,
        user_id=user_id,
        error_tool_name="automation_run_wait",
    )
    if run_record is None:
        return {"run": None}
    if _is_terminal_run(run_record):
        return {"run": run_record}
    run_record = await ensure_automation_run_owner_task_attached(
        utility_tools.database_automation_runs,
        utility_tools.task_registry,
        run_record=run_record,
    )
    owner_task_id = read_automation_run_owner_task_id(run_record)
    if owner_task_id is None:
        raise MCPToolError(-32603, "Automation run is active but has no owned task.")
    task = await utility_tools.task_registry.get(owner_task_id, force_refresh=True)
    if task is None or task.user_id != user_id:
        raise MCPToolError(-32602, "Automation task not found.")
    try:
        refreshed_run_record = await wait_for_owned_task_snapshot(
            utility_tools.task_registry,
            snapshot=run_record,
            owner_task_id=owner_task_id,
            timeout_ms=timeout_ms,
            can_wait=lambda current_run: not _is_terminal_run(current_run),
            reload_snapshot=lambda: _load_automation_run_snapshot(
                utility_tools,
                run_id=run_id,
                user_id=user_id,
                error_tool_name="automation_run_wait",
            ),
        )
    except SoAITimeoutError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    return {"run": refreshed_run_record}
