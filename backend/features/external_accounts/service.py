"""SoAI - External accounts service [backend/features/external_accounts/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.protocols import AsyncContextManagerProtocol
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.external_accounts.validation import (
    validate_external_account_create_payload,
    validate_external_account_update_payload,
)
from core.types.json import JSONDict
from features.external_accounts.account_locking import acquire_account_lock
from features.external_accounts.dependencies import ExternalAccountsServiceDependencies
from features.external_accounts.oauth_callback import (
    clear_oauth_method,
    complete_oauth_callback_method,
    get_oauth_status_method,
)
from features.external_accounts.oauth_start import start_oauth_method
from features.external_accounts.oauth_tokens import (
    build_xoauth2_sasl_method,
    get_access_token_method,
)

__all__ = ("ExternalAccountsService",)


class ExternalAccountsService(ExternalAccountsServiceProtocol):
    def __init__(self, deps: ExternalAccountsServiceDependencies) -> None:
        self.config = deps.config
        self.runtime_flags = deps.runtime_flags
        self.http_client = deps.http_client
        self.database_external_accounts = deps.database_external_accounts
        self.public_origin = self.config.get_str("SERVER.PUBLIC_ORIGIN")
        self.oauth_state_token_ttl_ms = max(
            1,
            int(self.config.get_int("TOOLS.MCP.OAUTH.STATE_TOKEN_TTL_MS")),
        )
        self.oauth_refresh_skew_ms = max(
            0,
            int(self.config.get_int("TOOLS.MCP.OAUTH.REFRESH_SKEW_MS")),
        )
        self._account_locks: TTLAsyncLockRegistry[tuple[int, str]] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=2000,
                cleanup_interval_seconds=300.0,
            ),
        )

    @override
    async def start_oauth(
        self,
        *,
        user_id: int,
        external_account_id: str,
        resource: str,
    ) -> JSONDict:
        return await start_oauth_method(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
            resource=resource,
        )

    @override
    async def get_oauth_status(self, *, user_id: int, external_account_id: str) -> JSONDict:
        return await get_oauth_status_method(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
        )

    @override
    async def clear_oauth(self, *, user_id: int, external_account_id: str) -> JSONDict:
        return await clear_oauth_method(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
        )

    @override
    async def complete_oauth_callback(
        self,
        *,
        code: str,
        state_token: str,
        user_id: int,
    ) -> JSONDict:
        return await complete_oauth_callback_method(
            self,
            code=code,
            state_token=state_token,
            user_id=user_id,
        )

    @override
    async def get_access_token(self, *, user_id: int, external_account_id: str) -> JSONDict:
        return await get_access_token_method(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
        )

    @override
    def build_xoauth2_sasl(self, *, user_email: str, access_token: str) -> str:
        return build_xoauth2_sasl_method(
            self,
            user_email=user_email,
            access_token=access_token,
        )

    @override
    def account_lock(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> AsyncContextManagerProtocol[None]:
        return acquire_account_lock(
            self._account_locks,
            user_id=user_id,
            account_id=external_account_id,
            label="external_account_id",
        )

    @override
    async def list_accounts(self, user_id: int) -> list[JSONDict]:
        return await self.database_external_accounts.list_accounts(user_id=user_id)

    @override
    async def get_account(
        self,
        user_id: int,
        external_account_id: str,
        *,
        decrypt_secrets: bool = False,
    ) -> JSONDict | None:
        return await self.database_external_accounts.get_account(
            user_id=user_id,
            external_account_id=external_account_id,
            decrypt_secrets=decrypt_secrets,
        )

    @override
    async def create_account(
        self,
        *,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict:
        validate_external_account_create_payload(payload)
        return await self.database_external_accounts.create_account(
            user_id=user_id,
            payload=payload,
        )

    @override
    async def update_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None:
        async with self.account_lock(
            user_id=user_id,
            external_account_id=external_account_id,
        ):
            current_account = await self.database_external_accounts.get_account(
                user_id=user_id,
                external_account_id=external_account_id,
                decrypt_secrets=False,
            )
            if current_account is None:
                return None
            validate_external_account_update_payload(
                current_account=current_account,
                updates=updates,
            )
            return await self.database_external_accounts.update_account(
                user_id=user_id,
                external_account_id=external_account_id,
                updates=updates,
            )

    @override
    async def delete_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> bool:
        async with self.account_lock(
            user_id=user_id,
            external_account_id=external_account_id,
        ):
            return await self.database_external_accounts.delete_account(
                user_id=user_id,
                external_account_id=external_account_id,
            )
