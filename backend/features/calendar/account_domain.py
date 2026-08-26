"""SoAI - Calendar linked-account policy [backend/features/calendar/account_domain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx2

from core.calendar.protocols import DatabaseCalendarProtocol
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.linked_account_definition import LinkedAccountDefinition
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.logging.trace import get_logger
from core.mail.protocols import DatabaseMailProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict
from core.validation.record_fields import require_optional_str
from features.calendar.account_payloads import extract_calendar_account_payload
from features.calendar.calendar_account_testing import test_calendar_account
from features.calendar.formatting import format_calendar_account
from features.external_accounts.account_locking import bind_account_lock
from features.mail.account_readiness import require_mail_account_compose_ready
from features.mail.runtime_state import load_mail_account_runtime

__all__ = (
    "CalendarAccountPolicy",
    "CalendarAccountPolicyDependencies",
)

LOGGER_NAME = "SoAI.features.calendar.account_domain"


@dataclass(frozen=True, slots=True)
class CalendarAccountPolicyDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    database_mail: DatabaseMailProtocol
    external_accounts: ExternalAccountsServiceProtocol
    calendar_account_locks: AsyncLockRegistryProtocol[tuple[int, str]]
    mail_account_locks: AsyncLockRegistryProtocol[tuple[int, str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CalendarAccountPolicyDependencies",
            calendar_account_locks=self.calendar_account_locks,
            config=self.config,
            database_calendar=self.database_calendar,
            database_mail=self.database_mail,
            external_accounts=self.external_accounts,
            http_client=self.http_client,
            mail_account_locks=self.mail_account_locks,
            runtime_flags=self.runtime_flags,
        )


class CalendarAccountPolicy:
    definition = LinkedAccountDefinition(
        account_type="calendar",
        domain_label="Calendar",
        owner="calendar",
        external_not_found_message="Calendar external account not found.",
        account_not_found_message="Calendar account not found.",
        account_not_found_after_update_message="Calendar account not found after update.",
    )

    def __init__(self, deps: CalendarAccountPolicyDependencies) -> None:
        self.config = deps.config
        self.runtime_flags = deps.runtime_flags
        self.http_client = deps.http_client
        self.database_calendar = deps.database_calendar
        self.database_mail = deps.database_mail
        self.external_accounts = deps.external_accounts
        self._account_locks = deps.calendar_account_locks
        self._mail_account_locks = deps.mail_account_locks
        self.account_lock = bind_account_lock(
            self._account_locks,
            label="account_id",
        )
        self.mail_account_lock = bind_account_lock(
            self._mail_account_locks,
            label="account_id",
        )
        self._logger = get_logger(LOGGER_NAME)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def extract_domain_payload(self, payload: JSONDict) -> JSONDict:
        return extract_calendar_account_payload(payload)

    def format_account(
        self,
        domain_account: JSONDict,
        external_account: JSONDict,
    ) -> JSONDict:
        return format_calendar_account(domain_account, external_account)

    async def validate_payload(self, *, user_id: int, payload: JSONDict) -> None:
        linked_mail_account_id = require_optional_str(
            extract_calendar_account_payload(payload).get("linked_mail_account_id"),
            label="linked_mail_account_id",
            build_error=ValidationError,
            invalid_message="linked_mail_account_id is invalid.",
        )
        if linked_mail_account_id is None:
            return
        async with self.mail_account_lock(
            user_id=user_id,
            account_id=linked_mail_account_id,
        ):
            linked_mail_account = await self.database_mail.get_account(
                user_id=user_id,
                account_id=linked_mail_account_id,
            )
            if linked_mail_account is None:
                raise ValidationError("Linked mail account not found.")
            try:
                runtime_state = await load_mail_account_runtime(
                    database_mail=self.database_mail,
                    external_accounts=self.external_accounts,
                    user_id=user_id,
                    account_id=linked_mail_account_id,
                    decrypt_secrets=False,
                )
                require_mail_account_compose_ready(
                    runtime_state.account,
                    runtime_state.external_account,
                )
            except (StateError, ValidationError) as exception:
                raise ValidationError("Linked mail account is invalid.") from exception

    async def test_account(self, *, user_id: int, account_id: str) -> JSONDict:
        return await test_calendar_account(
            self,
            user_id=user_id,
            account_id=account_id,
        )
