"""SoAI - Linked account mutation flows [backend/features/external_accounts/domain_account_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from functools import partial

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    run_idempotent_current_task_operation,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.types.json import JSONDict
from features.external_accounts.account_locking import acquire_account_lock
from features.external_accounts.account_payloads import extract_external_account_updates
from features.external_accounts.domain_account_identifiers import (
    require_domain_external_account_id,
)
from features.external_accounts.linked_account_dependencies import (
    LinkedAccountDependencies,
)
from features.external_accounts.rollback import restore_external_account

__all__ = ("LinkedAccountMutations",)

OPERATION = "features.external_accounts.domain_account_update"


class LinkedAccountMutations:
    def __init__(self, deps: LinkedAccountDependencies) -> None:
        self._deps = deps

    async def update_account(
        self,
        *,
        user_id: int,
        account_id: str,
        payload: JSONDict,
    ) -> JSONDict | None:
        external_updates = extract_external_account_updates(payload)
        domain_updates = self._deps.policy.extract_domain_payload(payload)
        if not external_updates and not domain_updates:
            raise ValidationError("No account updates were provided.")
        await self._deps.policy.validate_payload(user_id=user_id, payload=payload)
        async with acquire_account_lock(
            self._deps.account_locks,
            user_id=user_id,
            account_id=account_id,
            label="account_id",
        ):
            domain_account = await self._deps.storage.get_account(
                user_id=user_id,
                account_id=account_id,
            )
            if domain_account is None:
                return None
            external_account_id = self._require_external_account_id(domain_account)
            async with self._deps.external_accounts.account_lock(
                user_id=user_id,
                external_account_id=external_account_id,
            ):
                return await self._update_locked_account(
                    user_id=user_id,
                    account_id=account_id,
                    external_updates=external_updates,
                    domain_updates=domain_updates,
                )

    async def delete_account(self, *, user_id: int, account_id: str) -> bool:
        async with acquire_account_lock(
            self._deps.account_locks,
            user_id=user_id,
            account_id=account_id,
            label="account_id",
        ):
            domain_account = await self._deps.storage.get_account(
                user_id=user_id,
                account_id=account_id,
            )
            if domain_account is None:
                return False
            external_account_id = self._require_external_account_id(domain_account)
            async with self._deps.external_accounts.account_lock(
                user_id=user_id,
                external_account_id=external_account_id,
            ):
                locked_account = await self._deps.storage.get_account(
                    user_id=user_id,
                    account_id=account_id,
                )
                if locked_account is None:
                    return False
                locked_external_account_id = self._require_external_account_id(locked_account)
                deleted = await run_idempotent_current_task_operation(
                    partial(
                        self._deps.external_accounts.delete_account,
                        user_id=user_id,
                        external_account_id=locked_external_account_id,
                    ),
                )
                if deleted:
                    if current_task_has_pending_cancellation():
                        raise asyncio.CancelledError
                    return True
                current_account = await run_idempotent_current_task_operation(
                    partial(
                        self._deps.storage.get_account,
                        user_id=user_id,
                        account_id=account_id,
                    ),
                )
                if current_account is None:
                    if current_task_has_pending_cancellation():
                        raise asyncio.CancelledError
                    return True
                raise StateError(
                    self._deps.policy.definition.external_not_found_message,
                )

    async def _update_locked_account(
        self,
        *,
        user_id: int,
        account_id: str,
        external_updates: JSONDict,
        domain_updates: JSONDict,
    ) -> JSONDict | None:
        locked_account = await self._deps.storage.get_account(
            user_id=user_id,
            account_id=account_id,
        )
        if locked_account is None:
            return None
        external_account_id = self._require_external_account_id(locked_account)
        previous_external: JSONDict | None = None
        if external_updates:
            previous_external = await self._update_external_before_domain(
                user_id=user_id,
                external_account_id=external_account_id,
                external_updates=external_updates,
            )
        domain_write_completed = False
        formatted_account: JSONDict | None = None
        external_restore_started = False
        try:
            if domain_updates:
                updated_account = await run_idempotent_current_task_operation(
                    partial(
                        self._deps.storage.update_account,
                        user_id=user_id,
                        account_id=account_id,
                        updates=domain_updates,
                    ),
                )
                if updated_account is None:
                    if previous_external is not None:
                        external_restore_started = True
                        await self._restore_external(
                            user_id,
                            external_account_id,
                            previous_external,
                        )
                        previous_external = None
                    if current_task_has_pending_cancellation():
                        raise asyncio.CancelledError
                    return None
                domain_write_completed = True
                if current_task_has_pending_cancellation():
                    raise asyncio.CancelledError
            formatted_account = await self._format_refreshed_account(
                user_id=user_id,
                account_id=account_id,
                external_account_id=external_account_id,
            )
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError
        except asyncio.CancelledError:
            if previous_external is not None and not domain_write_completed:
                await self._restore_external(
                    user_id,
                    external_account_id,
                    previous_external,
                )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if external_restore_started:
                raise
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                self._deps.policy.logger,
                coerced,
                message="Failed to update linked domain account.",
                operation=OPERATION,
                details={
                    "owner": self._deps.policy.definition.owner,
                    "user_id": user_id,
                    "account_id": account_id,
                    "external_account_id": external_account_id,
                },
            )
            if previous_external is not None and not domain_write_completed:
                await self._restore_external(
                    user_id,
                    external_account_id,
                    previous_external,
                )
            raise
        if formatted_account is None:
            raise StateError(
                self._deps.policy.definition.account_not_found_after_update_message,
            )
        return formatted_account

    async def _update_external_before_domain(
        self,
        *,
        user_id: int,
        external_account_id: str,
        external_updates: JSONDict,
    ) -> JSONDict:
        previous_external = await self._deps.external_accounts.get_account(
            user_id,
            external_account_id,
            decrypt_secrets=True,
        )
        if previous_external is None:
            raise StateError(self._deps.policy.definition.external_not_found_message)
        updated_external = await run_idempotent_current_task_operation(
            partial(
                self._deps.external_accounts.update_account,
                user_id=user_id,
                external_account_id=external_account_id,
                updates=external_updates,
            ),
        )
        if updated_external is None:
            raise StateError(self._deps.policy.definition.external_not_found_message)
        if current_task_has_pending_cancellation():
            await self._restore_external(user_id, external_account_id, previous_external)
            raise asyncio.CancelledError
        return previous_external

    async def _format_refreshed_account(
        self,
        *,
        user_id: int,
        account_id: str,
        external_account_id: str,
    ) -> JSONDict:
        refreshed_account = await self._deps.storage.get_account(
            user_id=user_id,
            account_id=account_id,
        )
        if refreshed_account is None:
            raise StateError(
                self._deps.policy.definition.account_not_found_after_update_message,
            )
        refreshed_external = await self._deps.external_accounts.get_account(
            user_id,
            external_account_id,
        )
        if refreshed_external is None:
            raise StateError(self._deps.policy.definition.external_not_found_message)
        return self._deps.policy.format_account(refreshed_account, refreshed_external)

    async def _restore_external(
        self,
        user_id: int,
        external_account_id: str,
        previous_account: JSONDict,
    ) -> None:
        await restore_external_account(
            external_accounts=self._deps.external_accounts,
            user_id=user_id,
            external_account_id=external_account_id,
            previous_account=previous_account,
            logger=self._deps.policy.logger,
            owner=self._deps.policy.definition.owner,
        )

    def _require_external_account_id(self, account: JSONDict) -> str:
        return require_domain_external_account_id(
            account,
            domain_label=self._deps.policy.definition.domain_label,
        )
