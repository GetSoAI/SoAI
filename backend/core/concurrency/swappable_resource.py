"""SoAI - Atomically swappable resource with generation tracking [backend/core/concurrency/swappable_resource.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

__all__ = (
    "ResourceBinding",
    "SwappableResource",
)


@dataclass(frozen=True, slots=True)
class ResourceBinding[T]:
    resource: T
    swap_event: asyncio.Event
    generation: int


class SwappableResource[T]:
    __slots__ = ("current", "generation", "swap_event")

    def __init__(self, initial: T) -> None:
        self.current: T = initial
        self.generation: int = 0
        self.swap_event: asyncio.Event = asyncio.Event()

    def bind(self) -> ResourceBinding[T]:
        return ResourceBinding(
            resource=self.current,
            swap_event=self.swap_event,
            generation=self.generation,
        )

    def swap(self, new_resource: T) -> int:
        old_event = self.swap_event
        self.current = new_resource
        self.generation += 1
        self.swap_event = asyncio.Event()
        old_event.set()
        return self.generation

    def is_current_generation(self, generation: int) -> bool:
        return self.generation == generation
