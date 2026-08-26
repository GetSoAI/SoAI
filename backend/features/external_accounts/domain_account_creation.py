"""SoAI - Shared linked domain account creation flow [backend/features/external_accounts/domain_account_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.types.json import JSONDict
from features.external_accounts.account_payloads import extract_external_account_payload
from features.external_accounts.linked_account_dependencies import (
    LinkedAccountDependencies,
)
from features.external_accounts.rollback import rollback_external_account_creation

__all__ = ("LinkedAccountCreation",)

OPERATION = "features.external_accounts.domain_account_creation"


class LinkedAccountCreation:
    def __init__(self, deps: LinkedAccountDependencies) -> None:
        self._deps = deps

    async def create_account(self, *, user_id: int, payload: JSONDict) -> JSONDict:
        external_payload = extract_external_account_payload(payload)
        domain_payload = self._deps.policy.extract_domain_payload(payload)
        await self._deps.policy.validate_payload(user_id=user_id, payload=payload)
        external_account = await uncancel_then_cleanup(
            self._deps.external_accounts.create_account(
                user_id=user_id,
                payload=external_payload,
            ),
        )
        external_account_id_value = external_account.get("id")
        external_account_id = (
            external_account_id_value.strip() if isinstance(external_account_id_value, str) else ""
        )
        if not external_account_id:
            raise StateError("Created external account is missing its id.")
        if current_task_has_pending_cancellation():
            await self._rollback_creation(user_id, external_account_id)
            raise asyncio.CancelledError
        try:
            domain_account = await self._deps.storage.create_account(
                user_id=user_id,
                external_account_id=external_account_id,
                payload=domain_payload,
            )
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError
            formatted_account = self._deps.policy.format_account(
                domain_account,
                external_account,
            )
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError
        except asyncio.CancelledError:
            await self._rollback_creation(user_id, external_account_id)
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                self._deps.policy.logger,
                coerced,
                message="Failed to create domain account after external account creation.",
                operation=OPERATION,
                details={
                    "owner": self._deps.policy.definition.owner,
                    "user_id": user_id,
                    "external_account_id": external_account_id,
                },
            )
            await self._rollback_creation(user_id, external_account_id)
            raise
        return formatted_account

    async def _rollback_creation(self, user_id: int, external_account_id: str) -> None:
        await rollback_external_account_creation(
            external_accounts=self._deps.external_accounts,
            user_id=user_id,
            external_account_id=external_account_id,
            logger=self._deps.policy.logger,
            owner=self._deps.policy.definition.owner,
        )
