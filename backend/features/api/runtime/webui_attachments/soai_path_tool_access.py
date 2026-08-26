"""SoAI - SoAI path provider tool access resolution [backend/features/api/runtime/webui_attachments/soai_path_tool_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent_mcp_config import normalize_conversation_mcp_config
from core.agent_mode import normalize_agent_mode
from core.agent_tool_policy import resolve_mode_default_tools
from core.automation.automation_mcp_config import normalize_automation_mcp_settings
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.conversation_model_settings_resolution import (
    require_conversation_model_settings,
)
from core.errors.exceptions import ValidationError
from core.workspaces.conversation_workspace_path import (
    read_conversation_workspace_path_override,
    resolve_effective_conversation_workspace_path,
)
from core.workspaces.user_workspace_path import require_user_record_workspace_path
from features.agent.runtime.model_tool_calling import model_supports_tool_calling
from features.api.runtime.webui_attachments.projection_context import SoaiPathToolAccess

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("messages_include_soai_path", "resolve_soai_path_tool_access")

_FILE_ACCESS_TOOL_NAMES = frozenset(("read_file", "read_image", "read_video", "read_document"))
_FOLDER_ACCESS_TOOL_NAMES = frozenset(("list_dir",))


@dataclass(frozen=True, slots=True)
class _SoaiPathToolFlags:
    can_read_files: bool
    can_list_folders: bool


def messages_include_soai_path(messages: list[JSONDict]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "soai_path":
                return True
    return False


def _mcp_payload(settings: JSONDict) -> JSONDict | None:
    raw_mcp = settings.get("mcp")
    if raw_mcp is None:
        return None
    if not isinstance(raw_mcp, dict):
        raise ValidationError("Conversation MCP settings must be an object.")
    return raw_mcp


def _agent_mode(settings: JSONDict) -> str:
    agent_value = settings.get("agent")
    agent = agent_value if isinstance(agent_value, dict) else {}
    return normalize_agent_mode(agent.get("mode"), strict=False)


def _resolve_tool_flags(
    *,
    dependencies: ApiDependencies,
    settings: JSONDict,
    is_automation: bool,
) -> _SoaiPathToolFlags:
    if is_automation:
        normalized_mcp = normalize_automation_mcp_settings(
            _mcp_payload(settings),
            disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
                dependencies.config,
            ),
        )
    else:
        normalized_mcp = normalize_conversation_mcp_config(_mcp_payload(settings))
    if not normalized_mcp.tools_enabled:
        return _SoaiPathToolFlags(can_read_files=False, can_list_folders=False)
    selected_tool_names = resolve_mode_default_tools(
        agent_mode=_agent_mode(settings),
        default_tools=tuple(normalized_mcp.default_tools),
        plan_tools=tuple(normalized_mcp.plan_tools),
        execute_tools=tuple(normalized_mcp.execute_tools),
    )
    return _SoaiPathToolFlags(
        can_read_files=any(
            tool_name in _FILE_ACCESS_TOOL_NAMES for tool_name in selected_tool_names
        ),
        can_list_folders=any(
            tool_name in _FOLDER_ACCESS_TOOL_NAMES for tool_name in selected_tool_names
        ),
    )


async def resolve_soai_path_tool_access(
    *,
    dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
    model_id: str | None,
    messages: list[JSONDict],
) -> SoaiPathToolAccess | None:
    if model_id is None or not messages_include_soai_path(messages):
        return None
    if not await model_supports_tool_calling(dependencies, model_id):
        return None
    conversation = await dependencies.database_conversations.get_conversation(conv_id, user_id)
    if not isinstance(conversation, dict):
        raise ValidationError("Conversation record is unavailable for SoAI path projection.")
    settings = require_conversation_model_settings(
        conversation.get("model_settings"),
        exception_type=ValidationError,
    )
    flags = _resolve_tool_flags(
        dependencies=dependencies,
        settings=settings,
        is_automation=conversation.get("is_automation") in (1, True),
    )
    if not flags.can_read_files and not flags.can_list_folders:
        return None
    user = await dependencies.database_users.get_account_by_id(user_id)
    if user is None:
        raise ValidationError("User record is unavailable for SoAI path projection.")
    workspace_path = resolve_effective_conversation_workspace_path(
        files=dependencies.files,
        user_workspace_path=require_user_record_workspace_path(user),
        override_workspace_path=read_conversation_workspace_path_override(settings),
        require_existing_directories=True,
    )
    return SoaiPathToolAccess(
        workspace_path=workspace_path,
        can_read_files=flags.can_read_files,
        can_list_folders=flags.can_list_folders,
    )
