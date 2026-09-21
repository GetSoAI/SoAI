"""SoAI - Global registry for active WebUI WebSocket chat streams [backend/features/api/runtime/chat_stream_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.events.protocols import EventBusProtocol
from core.events.types_system import ChatStreamActivityChangedEvent
from core.logging.trace import get_logger
from features.api.runtime.chat_stream_registry_types import (
    ChatStreamCancellationIntent,
    ChatStreamRegistrySnapshot,
    ChatStreamReservation,
    chat_stream_registry_slot_accepts_runtime,
    execution_owns_runtime,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.concurrency.protocols import AsyncContextManagerProtocol

__all__ = (
    "ChatStreamCancellationIntent",
    "ChatStreamRegistry",
    "ChatStreamRegistryDependencies",
    "ChatStreamRegistrySnapshot",
    "ChatStreamReservation",
    "chat_stream_registry_slot_accepts_runtime",
)

LOGGER_NAME = "SoAI.features.api.chat_stream_registry"
OPERATION_PUBLISH_REGISTRATION = "api_runtime.chat_stream_registry.register.publish"
OPERATION_PUBLISH_REMOVAL = "api_runtime.chat_stream_registry.remove.publish"


@dataclass(frozen=True, slots=True)
class ChatStreamRegistryDependencies:
    event_bus: EventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(owner="ChatStreamRegistryDependencies", event_bus=self.event_bus)


class ChatStreamRegistry:
    __slots__ = (
        "_active_by_key",
        "_cancellation_intents_by_key",
        "_cancellation_tasks_by_key",
        "_deps",
        "_lifecycle_locks",
        "_lock",
        "_reservations_by_key",
    )

    def __init__(self, deps: ChatStreamRegistryDependencies) -> None:
        self._deps = deps
        self._lock = asyncio.Lock()
        self._lifecycle_locks = TTLAsyncLockRegistry[tuple[int, str]](
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=1800.0,
                max_size=5000,
                cleanup_interval_seconds=300.0,
            ),
        )
        self._active_by_key: dict[tuple[int, str], AssistantTimelineRuntime] = {}
        self._reservations_by_key: dict[tuple[int, str], ChatStreamReservation] = {}
        self._cancellation_intents_by_key: dict[tuple[int, str], ChatStreamCancellationIntent] = {}
        self._cancellation_tasks_by_key: dict[tuple[int, str], tuple[str, asyncio.Task[None]]] = {}

    def lifecycle_lock(
        self,
        *,
        user_id: int,
        conv_id: str,
    ) -> AsyncContextManagerProtocol[None]:
        return self._lifecycle_locks.lock((int(user_id), conv_id))

    async def try_register(self, runtime: AssistantTimelineRuntime) -> bool:
        key = (int(runtime.user_id), runtime.conv_id)
        async with self._lifecycle_locks.lock(key):
            async with self._lock:
                reservation = self._reservations_by_key.get(key)
                if reservation is not None and not execution_owns_runtime(
                    reservation.request_id, runtime
                ):
                    return False
                intent = self._cancellation_intents_by_key.get(key)
                if intent is not None and not execution_owns_runtime(intent.request_id, runtime):
                    return False
                existing = self._active_by_key.get(key)
                if (
                    existing is not None
                    and existing is not runtime
                    and not chat_stream_registry_slot_accepts_runtime(existing)
                ):
                    return False
                activity_changed = existing is None
                self._active_by_key[key] = runtime
                if intent is not None and execution_owns_runtime(intent.request_id, runtime):
                    runtime.cancellation_requested = True
                    runtime.cancellation_reason = intent.reason
                    if runtime.detach_event is None:
                        runtime.detach_event = asyncio.Event()
                    runtime.detach_event.set()
                if activity_changed:
                    try:
                        await self._publish_activity(
                            int(runtime.user_id),
                            self._active_conversation_ids_locked(int(runtime.user_id)),
                        )
                    except asyncio.CancelledError:
                        self._restore_registration_locked(key, existing, reservation)
                        raise
                    except Exception as exception:
                        self._restore_registration_locked(key, existing, reservation)
                        coerced = coerce_to_soai_error(
                            exception,
                            operation=OPERATION_PUBLISH_REGISTRATION,
                        )
                        log_exception(
                            get_logger(LOGGER_NAME),
                            coerced,
                            message="Chat stream registration activity publication failed.",
                            operation=OPERATION_PUBLISH_REGISTRATION,
                        )
                        raise
            return True

    async def try_reserve(self, reservation: ChatStreamReservation) -> bool:
        key = (int(reservation.user_id), reservation.conv_id)
        async with self._lifecycle_locks.lock(key):
            return await self.try_reserve_while_lifecycle_locked(reservation)

    async def try_reserve_while_lifecycle_locked(
        self,
        reservation: ChatStreamReservation,
    ) -> bool:
        key = (int(reservation.user_id), reservation.conv_id)
        async with self._lock:
            pending_intent = self._cancellation_intents_by_key.get(key)
            if pending_intent is not None and pending_intent.request_id != reservation.request_id:
                return False
            existing_reservation = self._reservations_by_key.get(key)
            if existing_reservation is not None:
                return existing_reservation == reservation
            existing_runtime = self._active_by_key.get(key)
            if not chat_stream_registry_slot_accepts_runtime(existing_runtime):
                return False
            self._reservations_by_key[key] = reservation
            return True

    async def remember_cancellation_intent(
        self,
        intent: ChatStreamCancellationIntent,
    ) -> None:
        key = (int(intent.user_id), intent.conv_id)
        async with self._lock:
            existing = self._cancellation_intents_by_key.get(key)
            if existing is not None and existing.request_id != intent.request_id:
                raise StateError("A different Chat stream cancellation intent is still pending.")
            if (
                existing is not None
                and existing.force_pending_steers != intent.force_pending_steers
            ):
                return
            self._cancellation_intents_by_key[key] = intent

    async def cancellation_task_for(
        self,
        *,
        user_id: int,
        conv_id: str,
        request_id: str,
    ) -> asyncio.Task[None] | None:
        key = (int(user_id), conv_id)
        async with self._lock:
            entry = self._cancellation_tasks_by_key.get(key)
            if entry is None or entry[0] != request_id:
                return None
            if entry[1].done() and (entry[1].cancelled() or entry[1].exception() is not None):
                del self._cancellation_tasks_by_key[key]
                return None
            return entry[1]

    async def record_cancellation_task(
        self,
        *,
        user_id: int,
        conv_id: str,
        request_id: str,
        task: asyncio.Task[None],
    ) -> None:
        key = (int(user_id), conv_id)
        async with self._lock:
            existing = self._cancellation_tasks_by_key.get(key)
            if existing is not None and existing[0] == request_id:
                raise StateError("Cancellation task already exists for request identity.")
            self._cancellation_tasks_by_key[key] = (request_id, task)

    async def release_reservation(self, reservation: ChatStreamReservation) -> None:
        key = (int(reservation.user_id), reservation.conv_id)
        async with self._lock:
            existing = self._reservations_by_key.get(key)
            if existing == reservation:
                del self._reservations_by_key[key]

    async def clear_cancellation_intent_if_same(
        self,
        *,
        user_id: int,
        conv_id: str,
        request_id: str,
    ) -> None:
        key = (int(user_id), conv_id)
        async with self._lock:
            intent = self._cancellation_intents_by_key.get(key)
            if intent is not None and intent.request_id == request_id:
                del self._cancellation_intents_by_key[key]
            task_entry = self._cancellation_tasks_by_key.get(key)
            if task_entry is not None and task_entry[0] == request_id:
                del self._cancellation_tasks_by_key[key]

    async def snapshot(self, *, user_id: int, conv_id: str) -> ChatStreamRegistrySnapshot:
        key = (int(user_id), conv_id)
        async with self._lock:
            return ChatStreamRegistrySnapshot(
                runtime=self._active_by_key.get(key),
                reservation=self._reservations_by_key.get(key),
                cancellation_intent=self._cancellation_intents_by_key.get(key),
            )

    async def get(self, *, user_id: int, conv_id: str) -> AssistantTimelineRuntime | None:
        key = (int(user_id), conv_id)
        async with self._lock:
            return self._active_by_key.get(key)

    async def snapshot_active(self) -> tuple[AssistantTimelineRuntime, ...]:
        async with self._lock:
            return tuple(self._active_by_key.values())

    async def snapshot_active_conversation_ids(self, *, user_id: int) -> tuple[str, ...]:
        async with self._lock:
            return self._active_conversation_ids_locked(int(user_id))

    async def remove_if_same(self, runtime: AssistantTimelineRuntime) -> None:
        key = (int(runtime.user_id), runtime.conv_id)
        async with self._lock:
            existing = self._active_by_key.get(key)
            if existing is not runtime:
                return
            del self._active_by_key[key]
            try:
                await self._publish_activity(
                    int(runtime.user_id),
                    self._active_conversation_ids_locked(int(runtime.user_id)),
                )
            except asyncio.CancelledError:
                self._active_by_key[key] = runtime
                raise
            except Exception as exception:
                self._active_by_key[key] = runtime
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_PUBLISH_REMOVAL,
                )
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerced,
                    message="Chat stream removal activity publication failed.",
                    operation=OPERATION_PUBLISH_REMOVAL,
                )
                raise
            if runtime.terminal_persistence_completed:
                intent = self._cancellation_intents_by_key.get(key)
                if intent is not None and execution_owns_runtime(intent.request_id, runtime):
                    del self._cancellation_intents_by_key[key]
                task_entry = self._cancellation_tasks_by_key.get(key)
                if task_entry is not None and execution_owns_runtime(task_entry[0], runtime):
                    del self._cancellation_tasks_by_key[key]

    def _restore_registration_locked(
        self,
        key: tuple[int, str],
        runtime: AssistantTimelineRuntime | None,
        reservation: ChatStreamReservation | None,
    ) -> None:
        if runtime is None:
            self._active_by_key.pop(key, None)
        else:
            self._active_by_key[key] = runtime
        if reservation is None:
            self._reservations_by_key.pop(key, None)
        else:
            self._reservations_by_key[key] = reservation

    def _active_conversation_ids_locked(self, user_id: int) -> tuple[str, ...]:
        return tuple(
            sorted(
                conversation_id
                for candidate_user_id, conversation_id in self._active_by_key
                if candidate_user_id == user_id
            ),
        )

    async def _publish_activity(
        self,
        user_id: int,
        active_conversation_ids: tuple[str, ...],
    ) -> None:
        await self._deps.event_bus.publish(
            ChatStreamActivityChangedEvent(
                user_id=user_id,
                active_conversation_ids=list(active_conversation_ids),
            ),
        )
