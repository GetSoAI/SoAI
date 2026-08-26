"""SoAI - Global registry for active WebUI WebSocket chat streams [backend/features/api/runtime/chat_stream_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.events.protocols import EventBusProtocol
from core.events.types_system import ChatStreamActivityChangedEvent
from core.logging.trace import get_logger
from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
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


def chat_stream_registry_slot_accepts_runtime(
    existing: AssistantTimelineRuntime | None,
) -> bool:
    if existing is None:
        return True
    if existing.terminal_persistence_completed:
        return True
    return (
        existing.cancellation_requested
        and existing.detach_event is not None
        and existing.detach_event.is_set()
    )


@dataclass(frozen=True, slots=True)
class ChatStreamReservation:
    user_id: int
    conv_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ChatStreamRegistrySnapshot:
    runtime: AssistantTimelineRuntime | None
    reservation: ChatStreamReservation | None


class ChatStreamRegistry:
    __slots__ = ("_active_by_key", "_deps", "_lock", "_reservations_by_key")

    def __init__(self, deps: ChatStreamRegistryDependencies) -> None:
        self._deps = deps
        self._lock = asyncio.Lock()
        self._active_by_key: dict[tuple[int, str], AssistantTimelineRuntime] = {}
        self._reservations_by_key: dict[tuple[int, str], ChatStreamReservation] = {}

    async def try_register(self, runtime: AssistantTimelineRuntime) -> bool:
        key = (int(runtime.user_id), runtime.conv_id)
        async with self._lock:
            reservation = self._reservations_by_key.get(key)
            if reservation is not None:
                if reservation.request_id != runtime.request_id:
                    return False
            existing = self._active_by_key.get(key)
            if existing is not None and existing is not runtime:
                if not chat_stream_registry_slot_accepts_runtime(existing):
                    return False
            activity_changed = existing is None
            self._active_by_key[key] = runtime
            if reservation is not None:
                del self._reservations_by_key[key]
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

    async def release_reservation(self, reservation: ChatStreamReservation) -> None:
        key = (int(reservation.user_id), reservation.conv_id)
        async with self._lock:
            existing = self._reservations_by_key.get(key)
            if existing == reservation:
                del self._reservations_by_key[key]

    async def snapshot(self, *, user_id: int, conv_id: str) -> ChatStreamRegistrySnapshot:
        key = (int(user_id), conv_id)
        async with self._lock:
            return ChatStreamRegistrySnapshot(
                runtime=self._active_by_key.get(key),
                reservation=self._reservations_by_key.get(key),
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
