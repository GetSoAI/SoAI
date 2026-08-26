"""SoAI - SoAI path link resolution records [backend/features/api/runtime/soai_links/resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.workspaces.soai_path_resolution import (
    build_soai_path_content_part,
    build_soai_path_draft_record,
    conversation_virtual_path_for_user_token,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.workspaces.soai_path_link_codec import DecodedSoaiPathToken
    from features.api.runtime.conversation_workspace_scope import (
        ConversationWorkspaceScope,
    )

__all__ = ("resolve_soai_path_draft_token", "resolve_soai_path_token")


def resolve_soai_path_token(
    *,
    scope: ConversationWorkspaceScope,
    token: DecodedSoaiPathToken,
) -> JSONDict:
    conversation_virtual_path = conversation_virtual_path_for_user_token(
        user_root=scope.user_root_scope.root_path,
        effective_workspace_root=scope.effective_root_real,
        token=token,
    )
    return build_soai_path_content_part(
        effective_workspace_root=scope.effective_root_real,
        root_fingerprint=scope.root_fingerprint,
        conversation_virtual_path=conversation_virtual_path,
    )


def resolve_soai_path_draft_token(
    *,
    scope: ConversationWorkspaceScope,
    token: DecodedSoaiPathToken,
) -> JSONDict:
    return build_soai_path_draft_record(
        user_root=scope.user_root_scope.root_path,
        effective_workspace_root=scope.effective_root_real,
        root_fingerprint=scope.root_fingerprint,
        token=token,
    )
