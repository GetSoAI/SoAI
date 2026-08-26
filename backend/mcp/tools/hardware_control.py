"""SoAI - MCP internal utility tool: hardware_control [backend/mcp/tools/hardware_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.control_requests import (
    parse_required_device_id,
    parse_settings,
)
from mcp.tools.admin_privileges import require_admin_user
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.hardware_internal_context import (
    require_hardware_internal_execute_context,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_hardware_control",)


async def tool_hardware_control(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    action = _parse_action(arguments)
    user_id = require_authenticated_user_id(
        utility_tools,
        tool_name="hardware_control",
        message="User authentication required for hardware_control.",
    )
    await require_admin_user(utility_tools, user_id=user_id, tool_name="hardware_control")
    require_hardware_internal_execute_context(utility_tools, tool_name="hardware_control")
    if action == "list":
        return await utility_tools.hardware_control.list_gpu_controls()
    if action == "set":
        device_id = parse_required_device_id(arguments)
        settings = parse_settings(arguments)
        return await utility_tools.hardware_control.set_gpu_controls(
            device_id=device_id,
            settings=settings,
            created_by_user_id=user_id,
        )
    raise ValidationError(f"Unsupported hardware_control action: {action}")


def _parse_action(arguments: JSONDict) -> str:
    action = arguments.get("action")
    if not isinstance(action, str) or not action.strip():
        raise ValidationError("action is required.")
    normalized = action.strip()
    if normalized not in {"list", "set"}:
        raise ValidationError(f"Unsupported hardware_control action: {normalized}")
    return normalized
