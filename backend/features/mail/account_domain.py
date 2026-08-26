"""SoAI - Mail linked-account policy [backend/features/mail/account_domain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.external_accounts.linked_account_definition import LinkedAccountDefinition
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.logging.trace import get_logger
from core.mail.protocols import DatabaseMailProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict
from features.external_accounts.account_locking import bind_account_lock
from features.mail.account_payloads import extract_mail_account_payload
from features.mail.formatting import format_mail_account
from features.mail.imap_reads import run_imap_connectivity_check_sync
from features.mail.pop3_reads import run_pop3_connectivity_check_sync
from features.mail.smtp_transport import test_smtp_transport_sync
from features.mail.transport_preparation import prepare_service_mail_transport_context

__all__ = (
    "MailAccountPolicy",
    "MailAccountPolicyDependencies",
)

LOGGER_NAME = "SoAI.features.mail.account_domain"


@dataclass(frozen=True, slots=True)
class MailAccountPolicyDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    database_mail: DatabaseMailProtocol
    external_accounts: ExternalAccountsServiceProtocol
    mail_blocking_pool: BoundedBlockingPool
    account_locks: AsyncLockRegistryProtocol[tuple[int, str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MailAccountPolicyDependencies",
            account_locks=self.account_locks,
            config=self.config,
            database_mail=self.database_mail,
            external_accounts=self.external_accounts,
            mail_blocking_pool=self.mail_blocking_pool,
            runtime_flags=self.runtime_flags,
        )


class MailAccountPolicy:
    definition = LinkedAccountDefinition(
        account_type="mail",
        domain_label="Mail",
        owner="mail",
        external_not_found_message="Mail external account not found.",
        account_not_found_message="Mail account not found.",
        account_not_found_after_update_message="Mail account not found after update.",
    )

    def __init__(self, deps: MailAccountPolicyDependencies) -> None:
        self.config = deps.config
        self.runtime_flags = deps.runtime_flags
        self.database_mail = deps.database_mail
        self.external_accounts = deps.external_accounts
        self.mail_blocking_pool = deps.mail_blocking_pool
        self._account_locks = deps.account_locks
        self.account_lock = bind_account_lock(
            self._account_locks,
            label="account_id",
        )
        self._logger = get_logger(LOGGER_NAME)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def extract_domain_payload(self, payload: JSONDict) -> JSONDict:
        return extract_mail_account_payload(payload)

    def format_account(
        self,
        domain_account: JSONDict,
        external_account: JSONDict,
    ) -> JSONDict:
        return format_mail_account(domain_account, external_account)

    async def validate_payload(self, *, user_id: int, payload: JSONDict) -> None:
        _ = user_id
        _ = payload

    async def test_account(self, *, user_id: int, account_id: str) -> JSONDict:
        prepared = await prepare_service_mail_transport_context(
            self,
            user_id=user_id,
            account_id=account_id,
        )
        connect_timeout_sec = float(
            self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.CONNECT_SEC"),
        )
        inbound_check = (
            run_imap_connectivity_check_sync
            if prepared.runtime_state.protocol == "imap"
            else run_pop3_connectivity_check_sync
        )
        inbound_result = await run_bounded_blocking_call(
            self.mail_blocking_pool,
            partial(
                inbound_check,
                runtime_state=prepared.runtime_state,
                auth_payload=prepared.auth_payload,
                connect_timeout_sec=connect_timeout_sec,
                connect_host=prepared.inbound_connect_host,
            ),
            timeout_sec=connect_timeout_sec + 5.0,
        )
        smtp_result = await run_bounded_blocking_call(
            self.mail_blocking_pool,
            partial(
                test_smtp_transport_sync,
                runtime_state=prepared.runtime_state,
                auth_payload=prepared.auth_payload,
                connect_timeout_sec=connect_timeout_sec,
                connect_host=prepared.smtp_connect_host,
            ),
            timeout_sec=connect_timeout_sec + 5.0,
        )
        return {
            "account_id": account_id,
            "status": "ready",
            "protocol": prepared.runtime_state.protocol,
            "inbound": inbound_result,
            "smtp": smtp_result,
        }
