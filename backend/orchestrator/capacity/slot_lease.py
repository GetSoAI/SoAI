"""SoAI - Plugin slot lease context manager [backend/orchestrator/capacity/slot_lease.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

__all__ = ("PluginSlotLease",)


class PluginSlotLease:
    __slots__ = ("_plugin_name", "_release", "_released")

    def __init__(
        self,
        plugin_name: str,
        release: Callable[[], None] | None,
    ) -> None:
        self._plugin_name = plugin_name
        self._release = release
        self._released = False

    @staticmethod
    def noop(plugin_name: str) -> PluginSlotLease:
        return PluginSlotLease(plugin_name=plugin_name, release=None)

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        release = self._release
        if release is not None:
            release()

    async def __aenter__(self) -> PluginSlotLease:
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception_value: BaseException | None,
        _exception_traceback: TracebackType | None,
    ) -> None:
        self.release()
