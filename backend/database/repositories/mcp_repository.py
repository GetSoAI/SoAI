"""SoAI - Database repository for MCP server configuration and state [backend/database/repositories/mcp_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite
from cryptography.fernet import Fernet

from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from database.repositories.mcp_repository_reads import (
    read_all_mcp_servers,
    read_mcp_server,
)
from database.repositories.mcp_repository_write_contract import (
    ALLOWED_MCP_SERVER_UPDATE_COLS,
    ALLOWED_MCP_TRANSPORT_TYPES,
)
from database.repositories.mcp_repository_writes import (
    sync_add_mcp_server,
    sync_delete_mcp_server,
    sync_update_mcp_server,
)
from database.repositories.mcp_repository_writes_support import (
    serialize_mcp_capabilities,
    sync_update_mcp_server_capabilities,
    sync_update_mcp_server_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMCP",)


class DatabaseMCP:
    core: DatabaseCoreProtocol
    config: ConfigProtocol
    fernet: tuple[Fernet, ...]
    _ALLOWED_MCP_SERVER_UPDATE_COLS = ALLOWED_MCP_SERVER_UPDATE_COLS
    ALLOWED_MCP_TRANSPORT_TYPES = ALLOWED_MCP_TRANSPORT_TYPES

    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config
        self.fernet = deps.fernet

    async def _get_all_mcp_servers(
        self,
        database: aiosqlite.Connection,
        decrypt_key: bool = False,
    ) -> list[JSONDict]:
        return await read_all_mcp_servers(database, self.fernet, decrypt_key=decrypt_key)

    async def get_all_mcp_servers(self, decrypt_key: bool = False) -> list[JSONDict]:
        return await self.core.reader.execute_read(self._get_all_mcp_servers, decrypt_key)

    async def _get_mcp_server(
        self,
        database: aiosqlite.Connection,
        server_id: str,
        decrypt_key: bool = False,
    ) -> JSONDict | None:
        return await read_mcp_server(database, server_id, self.fernet, decrypt_key=decrypt_key)

    async def get_mcp_server(self, server_id: str, decrypt_key: bool = False) -> JSONDict | None:
        return await self.core.reader.execute_read(self._get_mcp_server, server_id, decrypt_key)

    async def add_mcp_server(
        self,
        server_id: str,
        name: str,
        transport_type: str,
        endpoint: str,
        args: list[str] | None,
        env: dict[str, str] | None,
        headers: dict[str, str] | None,
        api_key: str | None,
        timeout_ms: int,
        auto_reconnect: bool,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_add_mcp_server,
            self.fernet,
            server_id,
            name,
            transport_type,
            endpoint,
            args,
            env,
            headers,
            api_key,
            timeout_ms,
            auto_reconnect,
        )

    async def update_mcp_server_status(
        self,
        server_id: str,
        status: str,
        error: str | None = None,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_update_mcp_server_status,
            server_id,
            status,
            error,
        )

    async def update_mcp_server_capabilities(
        self,
        server_id: str,
        capabilities: JSONDict | None,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_update_mcp_server_capabilities,
            server_id,
            serialize_mcp_capabilities(capabilities),
        )

    async def update_mcp_server(self, server_id: str, updates: JSONDict) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_update_mcp_server,
            self.fernet,
            server_id,
            updates,
        )

    async def delete_mcp_server(self, server_id: str) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_delete_mcp_server,
            server_id,
        )
