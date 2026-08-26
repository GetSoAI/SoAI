"""SoAI - Conversation attention presence and render coordinator [backend/features/chat/attention/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies

__all__ = (
    "ConversationAttentionCoordinator",
    "ConversationAttentionCoordinatorDependencies",
)

ACK_TTL_SECONDS = 60.0
PRESENCE_TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class PresenceKey:
    user_id: int
    device_id: str
    tab_id: str


@dataclass(frozen=True, slots=True)
class AttentionKey:
    user_id: int
    conversation_id: str
    interaction_type: str
    task_id: str
    notification_id: str


@dataclass(frozen=True, slots=True)
class PresenceRecord:
    conversation_id: str | None
    is_visible: bool
    has_focus: bool
    updated_at: float


@dataclass(frozen=True, slots=True)
class ConversationAttentionCoordinatorDependencies:
    monotonic_clock: Callable[[], float]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConversationAttentionCoordinatorDependencies",
            monotonic_clock=self.monotonic_clock,
        )


class ConversationAttentionCoordinator:
    def __init__(self, deps: ConversationAttentionCoordinatorDependencies) -> None:
        self._monotonic_clock = deps.monotonic_clock
        self._presence: dict[PresenceKey, PresenceRecord] = {}
        self._acknowledged: dict[AttentionKey, float] = {}

    def update_presence(
        self,
        *,
        user_id: int,
        device_id: str,
        tab_id: str,
        conversation_id: str | None,
        is_visible: bool,
        has_focus: bool,
    ) -> None:
        self._prune()
        presence_key = PresenceKey(
            user_id=int(user_id),
            device_id=device_id,
            tab_id=tab_id,
        )
        if conversation_id is None or not is_visible or not has_focus:
            self._presence.pop(presence_key, None)
            return
        self._presence[presence_key] = PresenceRecord(
            conversation_id=conversation_id,
            is_visible=bool(is_visible),
            has_focus=bool(has_focus),
            updated_at=self._monotonic_clock(),
        )

    def remove_presence(self, *, user_id: int, device_id: str, tab_id: str) -> None:
        self._presence.pop(
            PresenceKey(user_id=int(user_id), device_id=device_id, tab_id=tab_id),
            None,
        )

    def has_active_conversation_presence(self, *, user_id: int, conversation_id: str) -> bool:
        self._prune()
        for presence_key, presence_record in self._presence.items():
            if presence_key.user_id != int(user_id):
                continue
            if presence_record.conversation_id != conversation_id:
                continue
            if presence_record.is_visible and presence_record.has_focus:
                return True
        return False

    def has_render_ack(
        self,
        *,
        user_id: int,
        conversation_id: str,
        interaction_type: str,
        task_id: str,
        notification_id: str,
    ) -> bool:
        self._prune()
        return (
            self._build_attention_key(
                user_id=user_id,
                conversation_id=conversation_id,
                interaction_type=interaction_type,
                task_id=task_id,
                notification_id=notification_id,
            )
            in self._acknowledged
        )

    def acknowledge_rendered(
        self,
        *,
        user_id: int,
        conversation_id: str,
        interaction_type: str,
        task_id: str,
        notification_id: str,
    ) -> None:
        self._prune()
        attention_key = self._build_attention_key(
            user_id=user_id,
            conversation_id=conversation_id,
            interaction_type=interaction_type,
            task_id=task_id,
            notification_id=notification_id,
        )
        self._acknowledged[attention_key] = self._monotonic_clock()

    def _prune(self) -> None:
        now = self._monotonic_clock()
        expired_presence = [
            presence_key
            for presence_key, presence_record in self._presence.items()
            if now - presence_record.updated_at > PRESENCE_TTL_SECONDS
        ]
        for presence_key in expired_presence:
            self._presence.pop(presence_key, None)
        expired_acks = [
            attention_key
            for attention_key, acknowledged_at in self._acknowledged.items()
            if now - acknowledged_at > ACK_TTL_SECONDS
        ]
        for attention_key in expired_acks:
            self._acknowledged.pop(attention_key, None)

    def _build_attention_key(
        self,
        *,
        user_id: int,
        conversation_id: str,
        interaction_type: str,
        task_id: str,
        notification_id: str,
    ) -> AttentionKey:
        return AttentionKey(
            user_id=int(user_id),
            conversation_id=conversation_id,
            interaction_type=interaction_type,
            task_id=task_id,
            notification_id=notification_id,
        )
