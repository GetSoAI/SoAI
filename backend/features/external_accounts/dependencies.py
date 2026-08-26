"""SoAI - External accounts service dependencies [backend/features/external_accounts/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.external_accounts.protocols import DatabaseExternalAccountsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("ExternalAccountsServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ExternalAccountsServiceDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_external_accounts: DatabaseExternalAccountsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ExternalAccountsServiceDependencies",
            config=self.config,
            runtime_flags=self.runtime_flags,
            http_client=self.http_client,
            database_external_accounts=self.database_external_accounts,
        )
