"""SoAI - Coroutine-safe holder for dynamically updatable component context [backend/orchestrator/control/context_holder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from core.plugins.protocols_guardian import DirectorComponentContext

__all__ = ("ComponentContextHolder",)


class ComponentContextHolder:
    __slots__ = ("_value",)

    def __init__(self, initial_value: DirectorComponentContext | None = None) -> None:
        self._value = initial_value

    @property
    def value(self) -> DirectorComponentContext:
        if self._value is None:
            raise StateError(
                "Component context is not initialized.",
                operation="component_context_holder.get",
            )
        return self._value

    def update(self, new_value: DirectorComponentContext) -> None:
        self._value = new_value
