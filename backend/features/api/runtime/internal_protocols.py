"""SoAI - API runtime internal protocols [backend/features/api/runtime/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Protocol

from starlette.datastructures import State

from core.events.types_base import Event
from core.mcp.agent_config_normalization import NormalizedAgentMCPConfig
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from asyncio import Task

    type AttachmentParseCoroutineFactory = Callable[[], Coroutine[None, None, None]]

    from features.api.runtime.chat_stream_registry import (
        ChatStreamRegistrySnapshot,
        ChatStreamReservation,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "AppStateContainerProtocol",
    "AttachmentParseTaskRegistryProtocol",
    "AttachmentParseTaskSpawnerProtocol",
    "BackupServiceProtocol",
    "ChatStreamRegistryProtocol",
    "CommandConstructorProtocol",
    "ConversationMCPStateProtocol",
    "HasAppProtocol",
    "RuntimeWithLockProtocol",
)


class AttachmentParseTaskSpawnerProtocol(Protocol):
    async def __call__(
        self,
        attachment_id: str,
        awaitable: Coroutine[None, None, None],
    ) -> Task[None]: ...


class AttachmentParseTaskRegistryProtocol(Protocol):
    @property
    def active_count(self) -> int: ...

    async def schedule(
        self,
        attachment_id: str,
        coroutine_factory: AttachmentParseCoroutineFactory,
    ) -> Task[None]: ...

    async def cancel_and_wait(self, attachment_id: str) -> bool: ...

    async def shutdown(self) -> None: ...


class AppStateContainerProtocol(Protocol):
    @property
    def state(self) -> State: ...


class HasAppProtocol(Protocol):
    @property
    def app(self) -> AppStateContainerProtocol: ...


class BackupServiceProtocol(Protocol):
    def is_operational(self) -> bool: ...

    async def list_backups(self) -> list[JSONDict]: ...

    async def start_create_backup_task(self, *, user_id: int) -> str: ...

    async def start_verify_backup_task(self, backup_id: str, *, user_id: int) -> str: ...

    async def start_delete_backup_task(self, backup_id: str, *, user_id: int) -> str: ...

    async def start_restore_backup_task(self, backup_id: str, *, user_id: int) -> str: ...

    async def create_backup_export_archive(self, backup_id: str) -> str: ...


class ChatStreamRegistryProtocol(Protocol):
    async def try_register(self, runtime: AssistantTimelineRuntime) -> bool: ...

    async def release_reservation(self, reservation: ChatStreamReservation) -> None: ...

    async def snapshot(self, *, user_id: int, conv_id: str) -> ChatStreamRegistrySnapshot: ...

    async def get(
        self,
        *,
        user_id: int,
        conv_id: str,
    ) -> AssistantTimelineRuntime | None: ...

    async def snapshot_active(self) -> tuple[AssistantTimelineRuntime, ...]: ...

    async def snapshot_active_conversation_ids(self, *, user_id: int) -> tuple[str, ...]: ...

    async def remove_if_same(self, runtime: AssistantTimelineRuntime) -> None: ...


class CommandConstructorProtocol(Protocol):
    def __call__(
        self,
        *,
        reply_channel: asyncio.Queue[Event],
        context: RequestContext,
        **command_fields: JSONValue,
    ) -> Event: ...


class ConversationMCPKnowledgeStateProtocol(Protocol):
    @property
    def rag_enabled(self) -> bool: ...

    @property
    def document_count(self) -> int: ...

    @property
    def auto_managed(self) -> bool: ...

    @property
    def tools_locked(self) -> bool: ...

    @property
    def force_tools_enabled(self) -> bool: ...

    @property
    def ready(self) -> bool: ...

    @property
    def blocking_reason(self) -> str | None: ...


class ConversationMCPStateProtocol(Protocol):
    @property
    def settings(self) -> JSONDict: ...

    @property
    def is_automation(self) -> bool: ...

    @property
    def stored_normalized_mcp(self) -> NormalizedAgentMCPConfig: ...

    @property
    def effective_normalized_mcp(self) -> NormalizedAgentMCPConfig: ...

    @property
    def knowledge_state(self) -> ConversationMCPKnowledgeStateProtocol: ...


class RuntimeWithLockProtocol(Protocol):
    lock: asyncio.Lock
