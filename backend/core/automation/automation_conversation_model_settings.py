"""SoAI - Automation conversation model settings resolution [backend/core/automation/automation_conversation_model_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_interactive_tool_approval import (
    extract_interactive_tool_approval,
)
from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)

if TYPE_CHECKING:
    from core.automation.protocols_database import DatabaseAutomationsProtocol
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "resolve_automation_conversation_model_settings",
    "resolve_automation_effective_conversation_model_settings",
)


async def resolve_automation_conversation_model_settings(
    *,
    user_id: int,
    model_settings: JSONDict,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> JSONDict:
    resolved = await resolve_conversation_model_settings(
        user_id=user_id,
        model_settings_snapshot=model_settings,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
    )
    agent_settings_value = resolved.get("agent")
    agent_settings_payload = (
        dict(agent_settings_value) if isinstance(agent_settings_value, dict) else {}
    )
    agent_settings_payload["mode"] = "execute"
    resolved["agent"] = agent_settings_payload
    interactive_tool_approval = extract_interactive_tool_approval(resolved)
    mcp_value = resolved.get("mcp")
    mcp_payload = dict(mcp_value) if isinstance(mcp_value, dict) else {}
    mcp_payload["tools_enabled"] = True
    mcp_payload["tool_approval_required"] = interactive_tool_approval
    resolved["mcp"] = mcp_payload
    return resolved


async def resolve_automation_effective_conversation_model_settings(
    *,
    user_id: int,
    automation_id: str,
    executed_model_settings: JSONDict,
    database_automations: DatabaseAutomationsProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> JSONDict:
    automation = await database_automations.get_automation(automation_id, user_id)
    if automation is None:
        return dict(executed_model_settings)
    current_model_settings = automation.get("model_settings")
    if not isinstance(current_model_settings, dict):
        return dict(executed_model_settings)
    return await resolve_automation_conversation_model_settings(
        user_id=user_id,
        model_settings=current_model_settings,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
    )
