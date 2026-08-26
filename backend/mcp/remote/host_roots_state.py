"""SoAI - MCP host roots normalization, persistence, and notifications [backend/mcp/remote/host_roots_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import quote, urlparse
from urllib.request import pathname2url

from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.jsonrpc import build_jsonrpc_notification
from mcp.protocol.types import MCPJSONRPCError, MCPServerStatus
from mcp.remote.internal_protocols import PersistSettingProtocol

if TYPE_CHECKING:
    from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol

__all__ = ("MCPHostRootsState",)


@dataclass(slots=True)
class MCPHostRootsState:
    connection_registry: MCPConnectionRegistryProtocol
    send_message: Callable[[MCPServerConnection, JSONDict], Awaitable[None]]
    persist_setting: PersistSettingProtocol
    setting_key: str
    list_changed_enabled: bool
    initial_roots: list[JSONValue] = field(default_factory=list[JSONValue])
    _roots: list[JSONDict] = field(default_factory=list[JSONDict], init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _cache: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._roots = self.normalize(self.initial_roots)

    def _stable_json(self, value: JSONValue) -> str:
        return serialize_json_compact_stable(value)

    def _path_to_file_uri(self, raw_path: str) -> tuple[str, str]:
        expanded = os.path.expanduser(raw_path)
        resolved = os.path.realpath(expanded)
        if not resolved:
            raise MCPJSONRPCError(-32602, "Invalid root path")
        if re.match(r"^[A-Za-z]:[\\\\/]", resolved):
            normalized = resolved.replace("\\", "/")
            return (
                f"file:///{quote(normalized, safe=':/')}",
                os.path.basename(normalized) or resolved,
            )
        if not resolved.startswith("/"):
            return (f"file://{pathname2url(resolved)}", os.path.basename(resolved) or resolved)
        return (f"file://{quote(resolved, safe='/')}", os.path.basename(resolved) or resolved)

    def normalize(self, roots: Sequence[JSONValue] | None = None) -> list[JSONDict]:
        normalized: list[JSONDict] = []
        source = roots if roots is not None else self._roots
        for entry in source:
            if isinstance(entry, str):
                uri, name = self._path_to_file_uri(entry)
                normalized.append({"uri": uri, "name": name})
            elif isinstance(entry, dict):
                uri = str(entry.get("uri") or "").strip()
                if not uri:
                    raise MCPJSONRPCError(-32602, "Invalid root entry: missing uri")
                if urlparse(uri).scheme != "file":
                    raise MCPJSONRPCError(
                        -32602,
                        f"Invalid root uri scheme: {urlparse(uri).scheme}",
                    )
                normalized.append(
                    {
                        "uri": uri,
                        **({} if "name" not in entry else {"name": str(entry["name"])}),
                    },
                )
            else:
                raise MCPJSONRPCError(-32602, f"Invalid root entry type: {type(entry).__name__}")
        return normalized

    async def set(self, roots: list[JSONValue]) -> list[JSONDict]:
        async with self._lock:
            normalized = self.normalize(list(roots))
            self._roots.clear()
            self._roots.extend(normalized)
            serialized = self._stable_json(self._roots)
            changed = serialized != self._cache
            if changed:
                await self.persist_setting(self.setting_key, self._roots)
                self._cache = serialized
        if changed and self.list_changed_enabled:
            notification = build_jsonrpc_notification("notifications/roots/list_changed")
            async with self.connection_registry.connections_lock:
                connections = list(self.connection_registry.connections.values())
            for connection in connections:
                if connection.status == MCPServerStatus.CONNECTED:
                    await self.send_message(connection, notification)
        return list(self._roots)

    async def load_from_stored(self, stored_value: JSONValue) -> None:
        async with self._lock:
            if stored_value is None or not isinstance(stored_value, list):
                normalized = self.normalize(None)
                await self.persist_setting(self.setting_key, normalized)
                self._cache = self._stable_json(normalized)
            else:
                self._roots.clear()
                self._roots.extend(self.normalize(list(stored_value)))
                self._cache = self._stable_json(self._roots)
