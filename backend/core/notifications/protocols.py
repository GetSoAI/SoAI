"""SoAI - Notification subsystem protocols [backend/core/notifications/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("ConversationAttentionCoordinatorProtocol",)


class ConversationAttentionCoordinatorProtocol(Protocol):
    def update_presence(
        self,
        *,
        user_id: int,
        device_id: str,
        tab_id: str,
        conversation_id: str | None,
        is_visible: bool,
        has_focus: bool,
    ) -> None: ...

    def remove_presence(self, *, user_id: int, device_id: str, tab_id: str) -> None: ...

    def has_active_conversation_presence(self, *, user_id: int, conversation_id: str) -> bool: ...

    def has_render_ack(
        self,
        *,
        user_id: int,
        conversation_id: str,
        interaction_type: str,
        task_id: str,
        notification_id: str,
    ) -> bool: ...

    def acknowledge_rendered(
        self,
        *,
        user_id: int,
        conversation_id: str,
        interaction_type: str,
        task_id: str,
        notification_id: str,
    ) -> None: ...
