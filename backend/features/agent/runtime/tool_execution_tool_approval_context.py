"""SoAI - Agent tool-approval context resolution [backend/features/agent/runtime/tool_execution_tool_approval_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_approval.preferences import read_tool_approval_permissions

if TYPE_CHECKING:
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "ToolApprovalContext",
    "resolve_tool_approval_context",
)

OPERATION_AGENT_TOOL_EXECUTION_TOOL_APPROVAL_DEPS_MISSING = (
    "agent.tool_execution.tool_approval_dependencies_missing"
)


@dataclass(frozen=True, slots=True)
class ToolApprovalContext:
    task_registry: TaskRegistryProtocol
    approved_tool_permissions: set[str]


async def resolve_tool_approval_context(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    task_registry: TaskRegistryProtocol | None,
    database_users: DatabaseUsersProtocol | None,
) -> ToolApprovalContext | None:
    if (
        not tool_context.tool_approval_required
        or not request_context.interactive_tool_approval
        or tool_context.user_id <= 0
        or not bool(tool_context.conv_id.strip())
    ):
        return None
    if task_registry is None or database_users is None:
        raise ValidationError(
            "Tool approval is enabled but required dependencies are missing.",
            operation=OPERATION_AGENT_TOOL_EXECUTION_TOOL_APPROVAL_DEPS_MISSING,
        )
    approved_tool_permissions: set[str] = set()
    preferences = await database_users.get_user_preferences(int(tool_context.user_id))
    approved_tool_permissions.update(read_tool_approval_permissions(preferences))
    return ToolApprovalContext(
        task_registry=task_registry,
        approved_tool_permissions=approved_tool_permissions,
    )
