"""SoAI - MCP vault_secret_request task metadata and completion models [backend/mcp/tools/vault_secret_request_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.elicitation_vault_secret_request import require_vault_secret_request_scope
from core.tasks.enums import TaskStatus
from core.web.site_scope import SiteScope
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "decode_vault_secret_request_task_completion",
    "require_vault_secret_request_scope_or_fail",
)


async def decode_vault_secret_request_task_completion(
    utility_tools: MCPUtilityToolsProtocol,
    completed_task: Task | None,
) -> JSONDict:
    if completed_task is None:
        raise MCPToolError(-32603, "vault_secret_request task not found.")
    if completed_task.status == TaskStatus.COMPLETED:
        result = completed_task.result
        if not isinstance(result, dict):
            raise MCPToolError(-32603, "vault_secret_request task result is invalid.")
        if result.get("secret_handoff") is not True:
            raise MCPToolError(
                -32603, "vault_secret_request task did not produce a secret handoff."
            )
        secret_handle_store = utility_tools.secret_handle_store
        if secret_handle_store is None:
            raise MCPToolError(-32603, "Secret store is not configured.")
        tool_identity = utility_tools.active_tool_call_context.get()
        if tool_identity is None:
            raise MCPToolError(-32603, "Vault secret tool identity is unavailable.")
        claim_owner = f"{completed_task.task_id}:{tool_identity.call_id}"
        claimed = await utility_tools.task_registry.database_tasks.claim_interaction_secret(
            task_id=completed_task.task_id,
            user_id=completed_task.user_id,
            conv_id=completed_task.owner_id,
            claim_owner=claim_owner,
        )
        if claimed is None:
            raise MCPToolError(-32603, "vault_secret_request secret handoff expired.")
        secret_handle_store.forget_all_for_interaction_task(completed_task.task_id)
        secret_handle = secret_handle_store.create_handle(
            claimed.user_id,
            claimed.conv_id,
            claimed.scope,
            {"username": claimed.username, "password": claimed.password},
            interaction_secret_identity=claimed.identity,
        )
        saved_value = result.get("saved_credential_id")
        saved_credential_id = saved_value.strip() if isinstance(saved_value, str) else None
        return {
            "secret_handle": secret_handle,
            "saved_credential_id": saved_credential_id or None,
        }
    if completed_task.status == TaskStatus.CANCELLED:
        message = completed_task.error_message or "vault_secret_request was cancelled by the user"
        raise MCPToolError(-32603, message)
    if completed_task.status == TaskStatus.FAILED:
        message = completed_task.error_message or "vault_secret_request task failed"
        raise MCPToolError(-32603, message)
    raise MCPToolError(
        -32603,
        f"vault_secret_request task ended with unexpected status: {completed_task.status.value}",
    )


def require_vault_secret_request_scope_or_fail(metadata: Mapping[str, JSONValue]) -> SiteScope:
    scope = require_vault_secret_request_scope(metadata)
    if scope is None:
        raise MCPToolError(-32603, "vault_secret_request task scope is missing or invalid.")
    return scope
