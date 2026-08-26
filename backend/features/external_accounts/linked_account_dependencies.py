"""SoAI - Linked account flow dependencies [backend/features/external_accounts/linked_account_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.di.validation import require_dependencies
from core.external_accounts.protocols import (
    ExternalAccountsServiceProtocol,
    LinkedAccountPolicyProtocol,
    LinkedDomainAccountStorageProtocol,
)

__all__ = ("LinkedAccountDependencies",)


@dataclass(frozen=True, slots=True)
class LinkedAccountDependencies:
    storage: LinkedDomainAccountStorageProtocol
    external_accounts: ExternalAccountsServiceProtocol
    policy: LinkedAccountPolicyProtocol
    account_locks: AsyncLockRegistryProtocol[tuple[int, str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LinkedAccountDependencies",
            account_locks=self.account_locks,
            external_accounts=self.external_accounts,
            policy=self.policy,
            storage=self.storage,
        )
