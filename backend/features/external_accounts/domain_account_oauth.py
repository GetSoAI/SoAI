"""SoAI - Shared domain account OAuth helpers [backend/features/external_accounts/domain_account_oauth.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.external_accounts.state import normalize_oauth_status
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.external_accounts.account_locking import acquire_account_lock
from features.external_accounts.domain_account_actions import (
    format_account_action_result,
)
from features.external_accounts.domain_account_identifiers import (
    require_domain_external_account_id,
)
from features.external_accounts.domain_account_loading import require_linked_domain_account
from features.external_accounts.linked_account_dependencies import (
    LinkedAccountDependencies,
)

__all__ = ("LinkedAccountAuthorization",)


class LinkedAccountAuthorization:
    def __init__(self, deps: LinkedAccountDependencies) -> None:
        self._deps = deps

    async def start_oauth(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> JSONDict:
        result = await self._run_oauth_action(
            user_id=user_id,
            account_id=account_id,
            action=lambda external_account_id: self._deps.external_accounts.start_oauth(
                user_id=user_id,
                external_account_id=external_account_id,
                resource="",
            ),
        )
        redirect_url_value = result.get("redirect_url")
        redirect_url = redirect_url_value if isinstance(redirect_url_value, str) else None
        return self._format_oauth_result(
            account_id=account_id,
            payload=result,
            redirect_url=redirect_url,
        )

    async def get_oauth_status(self, *, user_id: int, account_id: str) -> JSONDict:
        result = await self._run_oauth_action(
            user_id=user_id,
            account_id=account_id,
            action=lambda external_account_id: self._deps.external_accounts.get_oauth_status(
                user_id=user_id,
                external_account_id=external_account_id,
            ),
        )
        return self._format_oauth_result(
            account_id=account_id,
            payload=result,
            redirect_url=None,
        )

    async def clear_oauth(self, *, user_id: int, account_id: str) -> JSONDict:
        result = await self._run_oauth_action(
            user_id=user_id,
            account_id=account_id,
            action=lambda external_account_id: self._deps.external_accounts.clear_oauth(
                user_id=user_id,
                external_account_id=external_account_id,
            ),
        )
        return self._format_oauth_result(
            account_id=account_id,
            payload=result,
            redirect_url=None,
        )

    async def _run_oauth_action(
        self,
        *,
        user_id: int,
        account_id: str,
        action: Callable[[str], Awaitable[JSONDict]],
    ) -> JSONDict:
        async with acquire_account_lock(
            self._deps.account_locks,
            user_id=user_id,
            account_id=account_id,
            label="account_id",
        ):
            account = await require_linked_domain_account(
                self._deps.storage,
                user_id=user_id,
                account_id=account_id,
                missing_message=self._deps.policy.definition.account_not_found_message,
            )
            external_account_id = self._require_external_account_id(account)
            async with self._deps.external_accounts.account_lock(
                user_id=user_id,
                external_account_id=external_account_id,
            ):
                locked_account = await require_linked_domain_account(
                    self._deps.storage,
                    user_id=user_id,
                    account_id=account_id,
                    missing_message=self._deps.policy.definition.account_not_found_message,
                )
                return await action(self._require_external_account_id(locked_account))

    def _require_external_account_id(self, account: JSONDict) -> str:
        return require_domain_external_account_id(
            account,
            domain_label=self._deps.policy.definition.domain_label,
        )

    def _format_oauth_result(
        self,
        *,
        account_id: str,
        payload: JSONDict,
        redirect_url: str | None,
    ) -> JSONDict:
        raw_status = normalize_oauth_status(payload.get("oauth_status"))
        return format_account_action_result(
            account_id=account_id,
            account_type=self._deps.policy.definition.account_type,
            status=raw_status,
            details=_build_oauth_details(payload, raw_status=raw_status),
            redirect_url=redirect_url,
        )


def _build_oauth_details(payload: JSONDict, *, raw_status: str) -> JSONDict:
    details: JSONDict = {
        "raw_status": raw_status,
    }
    expires_at_ms = payload.get("oauth_expires_at_ms")
    if is_strict_int(expires_at_ms):
        details["expires_at_ms"] = expires_at_ms
    has_refresh_token = payload.get("oauth_has_refresh_token")
    if isinstance(has_refresh_token, bool):
        details["has_refresh_token"] = has_refresh_token
    return details
