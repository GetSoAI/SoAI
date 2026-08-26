"""SoAI - Conversation workspace path schema [backend/features/api/schemas/conversation_workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import BaseModel

__all__ = (
    "ConversationWorkspacePathConfigResponse",
    "ConversationWorkspacePathConfigUpdate",
)


class ConversationWorkspacePathConfigResponse(BaseModel):
    conv_id: str
    workspace_path: str | None
    effective_workspace_path: str | None
    effective_root_fingerprint: str | None
    is_valid: bool
    validation_code: str | None
    validation_message: str | None


class ConversationWorkspacePathConfigUpdate(BaseModel):
    workspace_path: str | None = None
