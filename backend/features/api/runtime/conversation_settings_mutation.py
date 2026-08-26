"""SoAI - Conversation settings mutation authority [backend/features/api/runtime/conversation_settings_mutation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.conversations.settings_authority import ConversationSettingsAuthority
    from core.runtime.protocols import RequestProtocol

__all__ = ("require_conversation_settings_mutable",)


def require_conversation_settings_mutable(
    request: RequestProtocol,
    authority: ConversationSettingsAuthority,
) -> None:
    if not authority.is_read_only:
        return
    if authority.is_automation:
        raise_invalid_request(
            request,
            "Automation conversation settings are backend-owned and cannot be updated from chat.",
            error_type="automation_conversation_settings_read_only",
        )
    raise_invalid_request(
        request,
        "Messaging conversation settings are account-owned and cannot be updated from chat.",
        error_type="messaging_account_settings_read_only",
    )
