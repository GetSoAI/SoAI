"""SoAI - Workspace resolution for WebUI SoAI path provider projection [backend/features/api/runtime/webui_attachments/soai_path_workspace_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.conversations.conversation_model_settings_resolution import (
    require_conversation_model_settings,
)
from core.errors.exceptions import ValidationError
from core.workspaces.conversation_workspace_path import (
    fingerprint_conversation_workspace_root,
    read_conversation_workspace_path_override,
    resolve_effective_conversation_workspace_path,
)
from core.workspaces.user_workspace_path import require_user_record_workspace_path

if TYPE_CHECKING:
    from features.api.runtime.webui_attachments.projection_context import (
        WebuiAttachmentProjectionContext,
    )

__all__ = (
    "resolve_matching_soai_path_workspace",
    "soai_path_tool_workspace_matches",
)


async def resolve_matching_soai_path_workspace(
    context: WebuiAttachmentProjectionContext,
    *,
    stored_fingerprint: str,
) -> str | None:
    user = await context.dependencies.database_users.get_account_by_id(context.user_id)
    conversation = await context.dependencies.database_conversations.get_conversation(
        context.conv_id,
        context.user_id,
    )
    if user is None or conversation is None:
        return None
    workspace_path = require_user_record_workspace_path(user)
    model_settings = require_conversation_model_settings(
        conversation.get("model_settings"),
        exception_type=ValidationError,
    )
    effective_root = resolve_effective_conversation_workspace_path(
        files=context.dependencies.files,
        user_workspace_path=workspace_path,
        override_workspace_path=read_conversation_workspace_path_override(model_settings),
        require_existing_directories=True,
    )
    if fingerprint_conversation_workspace_root(effective_root) != stored_fingerprint:
        return None
    return effective_root


def soai_path_tool_workspace_matches(
    context: WebuiAttachmentProjectionContext,
    *,
    effective_root: str,
) -> bool:
    tool_access = context.soai_path_tool_access
    if tool_access is None:
        return False
    try:
        return os.path.samefile(tool_access.workspace_path, effective_root)
    except OSError:
        tool_path = os.path.realpath(os.path.abspath(tool_access.workspace_path))
        root_path = os.path.realpath(os.path.abspath(effective_root))
        return tool_path == root_path
