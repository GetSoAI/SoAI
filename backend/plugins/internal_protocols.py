"""SoAI - Plugins subsystem internal protocols [backend/plugins/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_operations import SendTaskCompleteEventCallable

__all__ = ("PluginCommandContextProtocol", "SendCompletionWithTaskProtocol")


@runtime_checkable
class PluginCommandContextProtocol(Protocol):
    task_id: str | None
    user_id: int
    mutation_fencing_token: int | None


class SendCompletionWithTaskProtocol(Protocol):
    async def __call__(
        self,
        reply_channel: asyncio.Queue[Event] | None,
        task_id: str | None,
        *,
        success: bool,
        message: str,
        error_code: int | None = None,
        mutation_fencing_token: int | None = None,
        task_registry: TaskRegistryProtocol,
        send_task_complete_event_callable: SendTaskCompleteEventCallable | None = None,
    ) -> None: ...
