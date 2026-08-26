"""SoAI - MCP storage and configuration protocols [backend/core/mcp/protocols_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DatabaseMCPProtocol",
    "DatabaseMemoryProtocol",
    "MCPServerConfigProtocol",
)


class DatabaseMemoryProtocol(Protocol):
    async def list_entities(self, user_id: int) -> list[JSONDict]: ...
    async def search_entities(
        self,
        user_id: int,
        query: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[JSONDict]: ...
    async def get_entity(self, user_id: int, name: str) -> JSONDict | None: ...
    async def replace_entity_observations_for_source(
        self,
        user_id: int,
        entity_name: str,
        source: str,
        contents: list[str],
        entity_type: str | None = None,
        delete_entity_if_empty: bool = False,
    ) -> None: ...
    async def store_graph(
        self,
        user_id: int,
        entities: list[JSONDict],
        observations: list[JSONDict],
        relations: list[JSONDict],
    ) -> JSONDict: ...
    async def delete_graph(
        self,
        user_id: int,
        entity_names: list[str],
        observation_ids: list[str],
        relation_ids: list[str],
    ) -> JSONDict: ...


class MCPServerConfigProtocol(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def transport_type(self) -> str: ...
    @property
    def endpoint(self) -> str: ...
    @property
    def args(self) -> Sequence[str] | None: ...
    @property
    def env(self) -> Mapping[str, str] | None: ...
    @property
    def headers(self) -> Mapping[str, str] | None: ...
    @property
    def auth_type(self) -> str: ...
    @property
    def api_key_encrypted(self) -> str | None: ...
    @property
    def oauth_status(self) -> str: ...
    @property
    def oauth_client_id(self) -> str | None: ...
    @property
    def oauth_client_secret_encrypted(self) -> str | None: ...
    @property
    def oauth_access_token_encrypted(self) -> str | None: ...
    @property
    def oauth_refresh_token_encrypted(self) -> str | None: ...
    @property
    def oauth_expires_at_ms(self) -> int | None: ...
    @property
    def oauth_resource_metadata_url(self) -> str | None: ...
    @property
    def oauth_auth_server_issuer(self) -> str | None: ...
    @property
    def oauth_authorization_endpoint(self) -> str | None: ...
    @property
    def oauth_token_endpoint(self) -> str | None: ...
    @property
    def oauth_registration_endpoint(self) -> str | None: ...
    @property
    def oauth_token_endpoint_auth_method(self) -> str | None: ...
    @property
    def oauth_scopes(self) -> Sequence[str] | None: ...
    @property
    def oauth_required_scopes(self) -> Sequence[str] | None: ...
    @property
    def timeout_sec(self) -> int: ...
    @property
    def auto_reconnect(self) -> bool: ...
    @property
    def enabled(self) -> bool: ...


class DatabaseMCPProtocol(Protocol):
    async def get_all_mcp_servers(self, decrypt_key: bool = False) -> list[JSONDict]: ...
    async def get_mcp_server(
        self,
        server_id: str,
        decrypt_key: bool = False,
    ) -> JSONDict | None: ...
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
    ) -> JSONDict | None: ...
    async def update_mcp_server_status(
        self,
        server_id: str,
        status: str,
        error: str | None = None,
    ) -> bool: ...
    async def update_mcp_server_capabilities(
        self,
        server_id: str,
        capabilities: JSONDict | None,
    ) -> bool: ...
    async def update_mcp_server(self, server_id: str, updates: JSONDict) -> JSONDict | None: ...
    async def delete_mcp_server(self, server_id: str) -> bool: ...
