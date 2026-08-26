"""SoAI - Plugin system types [backend/plugins/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("PluginStateTransitionError",)


class PluginStateTransitionError(StateError):
    def __init__(
        self,
        plugin_name: str,
        previous_state: str | None,
        requested_state: str,
        allowed_states: Iterable[str],
    ) -> None:
        allowed = list(allowed_states)
        super().__init__(
            f"Invalid transition for '{plugin_name}': {previous_state} -> {requested_state}. Allowed: {allowed}.",
            details={
                "plugin_name": plugin_name,
                "previous_state": previous_state,
                "requested_state": requested_state,
            },
        )
        self.plugin_name = plugin_name
        self.previous_state = previous_state
        self.requested_state = requested_state
        self.allowed_states = allowed

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.plugin_name, self.previous_state, self.requested_state, self.allowed_states),
            {},
        )
