"""SoAI - Conversation-scoped preview reference resolution context [backend/features/api/runtime/preview_contract_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.protocols import FileExplorerCoreProtocol
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from core.workspaces.user_workspace_path import resolve_user_record_workspace_access
from features.file_explorer.conversation_workspace_path import (
    inspect_conversation_workspace_path_config,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "ConversationPreviewScope",
    "load_conversation_preview_scope",
)


@dataclass(frozen=True, slots=True)
class ConversationPreviewScope:
    file_explorer_core: FileExplorerCoreProtocol
    user_root_scope: FileSystemRootScopeProtocol
    effective_root_real: str


async def load_conversation_preview_scope(
    api_dependencies: ApiDependencies,
    *,
    conv_id: str,
    user_id: int,
) -> ConversationPreviewScope | None:
    file_explorer_core = api_dependencies.file_explorer_core
    if file_explorer_core is None:
        return None
    user_record = await api_dependencies.database_users.get_account_by_id(user_id)
    if not isinstance(user_record, dict):
        return None
    workspace_value = user_record.get("workspace_path")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        return None
    resolve_user_record_workspace_access(
        api_dependencies.files,
        user_record,
    )
    conversation_record = await api_dependencies.database_conversations.get_conversation(
        conv_id,
        user_id,
    )
    if not isinstance(conversation_record, dict):
        return None
    model_settings_value = conversation_record.get("model_settings")
    if not isinstance(model_settings_value, dict):
        return None
    inspection = inspect_conversation_workspace_path_config(
        files=api_dependencies.files,
        user_workspace_path=workspace_value,
        model_settings=model_settings_value,
        require_existing_directories=True,
    )
    effective_root_real = inspection.effective_workspace_path
    if not isinstance(effective_root_real, str) or not effective_root_real:
        return None
    try:
        user_root_scope = file_explorer_core.create_workspace_scope(workspace_value)
    except ValidationError:
        return None
    return ConversationPreviewScope(
        file_explorer_core=file_explorer_core,
        user_root_scope=user_root_scope,
        effective_root_real=effective_root_real,
    )
