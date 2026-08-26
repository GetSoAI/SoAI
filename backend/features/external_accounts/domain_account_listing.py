"""SoAI - Shared linked domain account listing flow [backend/features/external_accounts/domain_account_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from features.external_accounts.account_locking import acquire_account_lock
from features.external_accounts.domain_account_actions import (
    format_account_action_result,
    format_account_list_result,
)
from features.external_accounts.domain_account_identifiers import (
    require_domain_account_id,
    require_domain_external_account_id,
)
from features.external_accounts.domain_account_loading import require_linked_domain_account
from features.external_accounts.linked_account_dependencies import (
    LinkedAccountDependencies,
)

__all__ = ("LinkedAccountQueries",)


class LinkedAccountQueries:
    def __init__(self, deps: LinkedAccountDependencies) -> None:
        self._deps = deps

    async def list_accounts(self, user_id: int) -> JSONDict:
        listed_accounts = await self._deps.storage.list_accounts(user_id=user_id)
        items: list[JSONDict] = []
        for listed_account in listed_accounts:
            account_id = self._require_account_id(listed_account)
            external_account_id = self._require_external_account_id(listed_account)
            async with self._deps.external_accounts.account_lock(
                user_id=user_id,
                external_account_id=external_account_id,
            ):
                current_account = await self._deps.storage.get_account(
                    user_id=user_id,
                    account_id=account_id,
                )
                if current_account is None:
                    continue
                current_external_account_id = self._require_external_account_id(current_account)
                external_account = await self._deps.external_accounts.get_account(
                    user_id,
                    current_external_account_id,
                )
                if external_account is None:
                    raise StateError(
                        self._deps.policy.definition.external_not_found_message,
                    )
                items.append(
                    self._deps.policy.format_account(current_account, external_account),
                )
        return format_account_list_result(items)

    async def test_account(self, *, user_id: int, account_id: str) -> JSONDict:
        async with acquire_account_lock(
            self._deps.account_locks,
            user_id=user_id,
            account_id=account_id,
            label="account_id",
        ):
            await require_linked_domain_account(
                self._deps.storage,
                user_id=user_id,
                account_id=account_id,
                missing_message=self._deps.policy.definition.account_not_found_message,
            )
            details = await self._deps.policy.test_account(
                user_id=user_id,
                account_id=account_id,
            )
            return format_account_action_result(
                account_id=account_id,
                account_type=self._deps.policy.definition.account_type,
                status="ready",
                details=details,
            )

    def _require_account_id(self, account: JSONDict) -> str:
        return require_domain_account_id(
            account,
            domain_label=self._deps.policy.definition.domain_label,
        )

    def _require_external_account_id(self, account: JSONDict) -> str:
        return require_domain_external_account_id(
            account,
            domain_label=self._deps.policy.definition.domain_label,
        )
