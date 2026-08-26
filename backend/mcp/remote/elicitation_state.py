"""SoAI - MCP URL elicitation state manager owning pending elicitations [backend/mcp/remote/elicitation_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from mcp.remote.internal_protocols import PersistSettingProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("MCPElicitationState",)


def _new_pending_elicitations() -> dict[str, dict[str, str]]:
    return {}


@dataclass(slots=True)
class MCPElicitationState:
    persist_setting: PersistSettingProtocol
    setting_key: str
    _pending: dict[str, dict[str, str]] = field(
        default_factory=_new_pending_elicitations,
        init=False,
    )
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _cache: str | None = field(default=None, init=False)

    def _stable_json(self, value: JSONValue) -> str:
        return serialize_json_compact_stable(value)

    async def _persist(self) -> None:
        serialized = self._stable_json(self._pending)
        if serialized != self._cache:
            await self.persist_setting(self.setting_key, self._pending)
            self._cache = serialized

    async def record(self, server_id: str, elicitation_id: str, task_id: str) -> None:
        async with self._lock:
            pending = self._pending.get(server_id)
            if pending is None:
                pending = {}
                self._pending[server_id] = pending
            pending[elicitation_id] = task_id
            await self._persist()

    async def clear(self, client_id: str, elicitation_id: str) -> bool:
        async with self._lock:
            pending = self._pending.get(client_id)
            if not pending or elicitation_id not in pending:
                return False
            del pending[elicitation_id]
            if not pending:
                self._pending.pop(client_id, None)
            await self._persist()
            return True

    async def clear_for_task(self, client_id: str, elicitation_id: str, task_id: str) -> bool:
        async with self._lock:
            pending = self._pending.get(client_id)
            if not pending or pending.get(elicitation_id) != task_id:
                return False
            del pending[elicitation_id]
            if not pending:
                self._pending.pop(client_id, None)
            await self._persist()
            return True

    def load_from_stored(self, stored_value: JSONValue) -> None:
        if not isinstance(stored_value, dict):
            return
        self._pending.clear()
        self._pending.update(
            {
                server_id: {
                    elicitation_id: task_id
                    for elicitation_id, task_id in elicitation_map.items()
                    if isinstance(elicitation_id, str) and isinstance(task_id, str)
                }
                for server_id, elicitation_map in stored_value.items()
                if isinstance(server_id, str) and isinstance(elicitation_map, dict)
            },
        )
