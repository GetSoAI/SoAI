"""SoAI - Event bus subscription registry [backend/core/events/bus_subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.events.bus_callback_identity import describe_callback
from core.events.types_base import Event
from core.logging.protocols import TraceLogger

__all__ = (
    "SubscriptionRegistry",
    "SubscriptionRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class SubscriptionRegistryDependencies:
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(owner="SubscriptionRegistryDependencies", logger=self.logger)


class SubscriptionRegistry:
    def __init__(self, deps: SubscriptionRegistryDependencies) -> None:
        self._deps = deps
        self._logger = deps.logger
        self._subscribers: dict[
            type[Event],
            list[Callable[[Event], Awaitable[None]]],
        ] = defaultdict(list)
        self.lock = threading.RLock()
        self._mro_cache: dict[type[Event], tuple[type[Event], ...]] = {}

    def subscribe(
        self,
        *,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        if not inspect.iscoroutinefunction(callback):
            raise ValidationError("Event bus callback must be a coroutine function (async def).")
        callback_identity = describe_callback(callback)
        did_add = self.add_subscription(event_type=event_type, callback=callback)
        if not did_add:
            self._logger.trace(
                "Duplicate subscription ignored for %s: %s",
                event_type.__name__,
                callback_identity,
            )

    def unsubscribe(
        self,
        *,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        removed = self.remove_subscription(event_type=event_type, callback=callback)
        if removed:
            return
        self._logger.warning(
            "Attempted to unsubscribe a non-existent callback for event %s",
            event_type.__name__,
        )

    def add_subscription(
        self,
        *,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> bool:
        with self.lock:
            sub_list = self._subscribers[event_type]
            if callback in sub_list:
                return False
            sub_list.append(callback)
            self._mro_cache.clear()
            return True

    def remove_subscription(
        self,
        *,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> int:
        with self.lock:
            sub_list = self._subscribers.get(event_type)
            if not sub_list:
                return 0
            removed = 0
            while callback in sub_list:
                sub_list.remove(callback)
                removed += 1
            if removed:
                self._mro_cache.clear()
                if not sub_list:
                    del self._subscribers[event_type]
            return removed

    def has_subscribers(self, event_type: type[Event]) -> bool:
        with self.lock:
            mro_tuple = self._mro_cache.get(event_type)
            if mro_tuple is None:
                mro_tuple = tuple(cls for cls in event_type.mro() if issubclass(cls, Event))
                self._mro_cache[event_type] = mro_tuple
            return any(bool(self._subscribers.get(cls)) for cls in mro_tuple)

    def collect_callbacks(self, event: Event) -> list[Callable[[Event], Awaitable[None]]]:
        event_type = type(event)
        callbacks: list[Callable[[Event], Awaitable[None]]] = []
        seen: set[Callable[[Event], Awaitable[None]]] = set()
        with self.lock:
            mro_tuple = self._mro_cache.get(event_type)
            if mro_tuple is None:
                mro_tuple = tuple(cls for cls in event_type.mro() if issubclass(cls, Event))
                self._mro_cache[event_type] = mro_tuple
            for cls in mro_tuple:
                for callback in self._subscribers.get(cls, []):
                    if callback not in seen:
                        callbacks.append(callback)
                        seen.add(callback)
        return callbacks
