"""SoAI - Conversation workspace path override resolution [backend/features/file_explorer/conversation_workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.workspace_path import resolve_workspace_real_path
from core.workspaces.conversation_workspace_path import (
    fingerprint_conversation_workspace_root,
    read_conversation_workspace_path_override,
    resolve_conversation_workspace_path_override_for_update,
)

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONDict

__all__ = (
    "ConversationWorkspacePathInspection",
    "inspect_conversation_workspace_path_config",
)


@dataclass(frozen=True, slots=True)
class ConversationWorkspacePathInspection:
    workspace_path: str | None
    effective_workspace_path: str | None
    effective_root_fingerprint: str | None
    is_valid: bool
    validation_code: str | None
    validation_message: str | None


def inspect_conversation_workspace_path_config(
    *,
    files: FilesPathResolverProtocol,
    user_workspace_path: str,
    model_settings: JSONDict,
    require_existing_directories: bool,
) -> ConversationWorkspacePathInspection:
    def _extract_validation_code(exception: ValidationError) -> str | None:
        details = exception.details
        if details is None:
            return None
        raw_reason = details.get("reason")
        if not isinstance(raw_reason, str):
            return None
        trimmed = raw_reason.strip()
        return trimmed or None

    try:
        override = read_conversation_workspace_path_override(model_settings)
    except ValidationError as exception:
        return ConversationWorkspacePathInspection(
            workspace_path=None,
            effective_workspace_path=None,
            effective_root_fingerprint=None,
            is_valid=False,
            validation_code=_extract_validation_code(exception),
            validation_message=exception.message,
        )
    if override is None:
        try:
            user_root_real = resolve_workspace_real_path(files, user_workspace_path)
            if require_existing_directories and (not os.path.isdir(user_root_real)):
                raise ValidationError(
                    "workspace_path must be an existing directory.",
                    details={"reason": "invalid_default_root"},
                )
            return ConversationWorkspacePathInspection(
                workspace_path=None,
                effective_workspace_path=user_root_real,
                effective_root_fingerprint=fingerprint_conversation_workspace_root(user_root_real),
                is_valid=True,
                validation_code=None,
                validation_message=None,
            )
        except ValidationError as exception:
            return ConversationWorkspacePathInspection(
                workspace_path=None,
                effective_workspace_path=None,
                effective_root_fingerprint=None,
                is_valid=False,
                validation_code=_extract_validation_code(exception),
                validation_message=exception.message,
            )
    try:
        effective = resolve_conversation_workspace_path_override_for_update(
            files=files,
            user_workspace_path=user_workspace_path,
            override_workspace_path=override,
            require_existing_directories=require_existing_directories,
        )
        return ConversationWorkspacePathInspection(
            workspace_path=override,
            effective_workspace_path=effective,
            effective_root_fingerprint=fingerprint_conversation_workspace_root(effective),
            is_valid=True,
            validation_code=None,
            validation_message=None,
        )
    except ValidationError as exception:
        return ConversationWorkspacePathInspection(
            workspace_path=override,
            effective_workspace_path=None,
            effective_root_fingerprint=None,
            is_valid=False,
            validation_code=_extract_validation_code(exception) or "invalid_override",
            validation_message=exception.message,
        )
