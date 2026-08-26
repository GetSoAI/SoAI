"""SoAI - MCP search provider API key persistence and encryption [backend/mcp/search/api_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.protocols_database import DatabasePluginsProtocol
from mcp.search.clients.client_base import SearchClientBase
from mcp.search.providers import (
    has_search_provider,
    list_supported_providers,
    normalize_search_provider_name,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SearchProviderApiKeys",)

LOGGER_NAME = "SoAI.mcp.search.api_keys"
OPERATION_MCP_SEARCH_SERVICE_RESOLVE_TOKEN = "mcp.search.service.resolve_api_key"
OPERATION_MCP_SEARCH_SERVICE_SET_TOKEN = "mcp.search.service.set_api_key"


SEARCH_PROVIDER_STORE_SETTING_NAME = "mcp_search_provider_store"
_MASKED_KEY_PLACEHOLDER = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"


class SearchProviderApiKeys:
    def __init__(
        self,
        database_plugins: DatabasePluginsProtocol,
        fernet: tuple[Fernet, ...],
        search_providers: tuple[tuple[str, type[SearchClientBase]], ...],
    ) -> None:
        self._database_plugins = database_plugins
        self._fernet = fernet
        self._search_providers = search_providers
        self._api_keys_encrypted: dict[str, str] = {}
        self._api_keys_lock = asyncio.Lock()

    def list_supported_providers(self) -> list[str]:
        return list_supported_providers(self._search_providers)

    def _has_provider(self, provider: str) -> bool:
        return has_search_provider(provider, self._search_providers)

    def build_search_api_key_entry(self, provider: str, has_key: bool) -> JSONDict:
        return {
            "provider": provider,
            "apiKeyMasked": _MASKED_KEY_PLACEHOLDER if has_key else None,
            "source": None,
        }

    async def load_search_api_keys_from_persistence(self) -> None:
        logger = get_logger(LOGGER_NAME)
        raw_value = await self._database_plugins.get_system_setting(
            SEARCH_PROVIDER_STORE_SETTING_NAME,
        )
        if not isinstance(raw_value, dict):
            return
        loaded: dict[str, str] = {}
        for key, value in raw_value.items():
            if not isinstance(key, str) or not key:
                continue
            if not isinstance(value, str) or not value:
                continue
            loaded[key] = value
        async with self._api_keys_lock:
            self._api_keys_encrypted = loaded
        logger.debug("Loaded %d search API keys from persistence", len(loaded))

    async def resolve_search_provider_api_key(self, provider: str) -> str | None:
        logger = get_logger(LOGGER_NAME)
        normalized = normalize_search_provider_name(provider, self._search_providers)
        if not normalized:
            return None
        async with self._api_keys_lock:
            encrypted = self._api_keys_encrypted.get(normalized)
        if not encrypted:
            return None
        try:
            return self._fernet[0].decrypt(encrypted.encode()).decode()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to decrypt search API key",
                operation=OPERATION_MCP_SEARCH_SERVICE_RESOLVE_TOKEN,
                details={"provider": normalized},
                level="warning",
            )
            return None

    async def list_search_provider_api_keys(self) -> list[JSONDict]:
        async with self._api_keys_lock:
            configured_providers = set(self._api_keys_encrypted.keys())
        configured_lower = {name.lower() for name in configured_providers}
        result: list[JSONDict] = []
        for provider, _provider_cls in self._search_providers:
            result.append(
                self.build_search_api_key_entry(provider, provider.lower() in configured_lower),
            )
        for provider in configured_providers:
            normalized = normalize_search_provider_name(provider, self._search_providers)
            if normalized and not self._has_provider(normalized):
                result.append(self.build_search_api_key_entry(normalized, True))
        return result

    async def set_search_provider_api_key(self, provider: str, api_key: str) -> JSONDict:
        logger = get_logger(LOGGER_NAME)
        normalized = normalize_search_provider_name(provider, self._search_providers)
        if not normalized:
            raise ValidationError("Search provider name is required.")
        trimmed_key = str(api_key or "").strip()
        if not trimmed_key:
            raise ValidationError("Search provider API key is required.")
        try:
            encrypted = self._fernet[0].encrypt(trimmed_key.encode()).decode()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to encrypt search API key",
                operation=OPERATION_MCP_SEARCH_SERVICE_SET_TOKEN,
                details={"provider": normalized},
            )
            raise StateError("Failed to encrypt search provider API key.") from exception
        async with self._api_keys_lock:
            self._api_keys_encrypted[normalized] = encrypted
            encrypted_keys_snapshot = dict(self._api_keys_encrypted)
        await self._database_plugins.set_system_setting(
            SEARCH_PROVIDER_STORE_SETTING_NAME,
            encrypted_keys_snapshot,
        )
        logger.info("Search API key set for provider: %s", normalized)
        return self.build_search_api_key_entry(normalized, True)

    async def delete_search_provider_api_key(self, provider: str) -> bool:
        logger = get_logger(LOGGER_NAME)
        normalized = normalize_search_provider_name(provider, self._search_providers)
        if not normalized:
            return False
        async with self._api_keys_lock:
            if normalized not in self._api_keys_encrypted:
                return False
            del self._api_keys_encrypted[normalized]
            encrypted_keys_snapshot = dict(self._api_keys_encrypted)
        await self._database_plugins.set_system_setting(
            SEARCH_PROVIDER_STORE_SETTING_NAME,
            encrypted_keys_snapshot,
        )
        logger.info("Search API key deleted for provider: %s", normalized)
        return True
