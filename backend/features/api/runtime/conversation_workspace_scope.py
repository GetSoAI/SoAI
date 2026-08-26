"""SoAI - Conversation effective workspace scope resolution [backend/features/api/runtime/conversation_workspace_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.conversation_model_settings_resolution import (
    require_conversation_model_settings,
)
from core.errors.exceptions import ValidationError
from core.workspaces.conversation_workspace_path import (
    fingerprint_conversation_workspace_root,
)
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.runtime.user_coercion import current_user_to_json_dict
from features.file_explorer.conversation_workspace_path import (
    inspect_conversation_workspace_path_config,
)

if TYPE_CHECKING:
    from core.files.protocols import FileExplorerCoreProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.user_types import CurrentUser

__all__ = ("ConversationWorkspaceScope", "build_conversation_workspace_scope")


@dataclass(frozen=True, slots=True)
class ConversationWorkspaceScope:
    file_explorer_core: FileExplorerCoreProtocol
    user_root_scope: FileSystemRootScopeProtocol
    effective_root_scope: FileSystemRootScopeProtocol
    effective_root_real: str
    root_fingerprint: str
    override_workspace_path: str | None
    override_is_valid: bool
    override_validation_message: str | None


def build_conversation_workspace_scope(
    *,
    current_user: CurrentUser,
    conversation_record: JSONDict,
    api_context: ApiContext,
) -> ConversationWorkspaceScope:
    file_explorer_core = api_context.dependencies.file_explorer_core
    if file_explorer_core is None:
        raise ValidationError("File explorer service is not available.")
    workspace_value = require_authenticated_user_workspace_path(current_user.get("workspace_path"))
    resolve_user_record_workspace_access(
        api_context.dependencies.files,
        current_user_to_json_dict(current_user),
    )
    model_settings_value = require_conversation_model_settings(
        conversation_record.get("model_settings"),
        exception_type=ValidationError,
    )
    inspection = inspect_conversation_workspace_path_config(
        files=api_context.dependencies.files,
        user_workspace_path=workspace_value,
        model_settings=model_settings_value,
        require_existing_directories=True,
    )
    if inspection.workspace_path is not None and not inspection.is_valid:
        raise ValidationError(
            inspection.validation_message or "Conversation workspace path override is invalid.",
        )
    if inspection.effective_workspace_path is None:
        raise ValidationError(
            inspection.validation_message or "Conversation workspace path resolution failed.",
        )
    user_root_scope = file_explorer_core.create_workspace_scope(workspace_value)
    effective_root_scope = file_explorer_core.create_workspace_scope(
        inspection.effective_workspace_path,
    )
    return ConversationWorkspaceScope(
        file_explorer_core=file_explorer_core,
        user_root_scope=user_root_scope,
        effective_root_scope=effective_root_scope,
        effective_root_real=inspection.effective_workspace_path,
        root_fingerprint=fingerprint_conversation_workspace_root(
            inspection.effective_workspace_path,
        ),
        override_workspace_path=inspection.workspace_path,
        override_is_valid=bool(inspection.is_valid),
        override_validation_message=inspection.validation_message,
    )
