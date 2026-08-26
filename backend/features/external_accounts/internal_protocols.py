"""SoAI - Internal external account service protocols [backend/features/external_accounts/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import httpx2

from core.external_accounts.protocols import ExternalAccountsServiceProtocol

if TYPE_CHECKING:
    from core.concurrency.protocols import AsyncContextManagerProtocol
    from core.external_accounts.protocols import DatabaseExternalAccountsProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("AccountLockAcquirer", "ExternalAccountsOAuthServiceProtocol")


class AccountLockAcquirer(Protocol):
    def __call__(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class ExternalAccountsOAuthServiceProtocol(ExternalAccountsServiceProtocol, Protocol):
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_external_accounts: DatabaseExternalAccountsProtocol
    public_origin: str | None
    oauth_state_token_ttl_ms: int
    oauth_refresh_skew_ms: int
