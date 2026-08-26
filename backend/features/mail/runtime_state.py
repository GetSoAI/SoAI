"""SoAI - Mail runtime state loading helpers [backend/features/mail/runtime_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.validation.strings import coerce_trimmed_str_or_empty
from features.external_accounts.linked_external_account_loading import (
    load_linked_external_account,
)
from features.mail.mail_account_context import require_mail_account_protocol
from features.mail.mail_record_context import (
    require_folder_account_id,
    require_folder_remote_mailbox,
)
from features.mail.transport_models import (
    MailAccountRuntimeState,
    MailFolderRuntimeState,
)

if TYPE_CHECKING:
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.mail.protocols import DatabaseMailProtocol
    from core.types.json import JSONDict

__all__ = (
    "load_mail_account_runtime",
    "load_mail_folder_runtime",
)


async def load_mail_account_runtime(
    *,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
    decrypt_secrets: bool,
) -> MailAccountRuntimeState:
    linked_account = await load_linked_external_account(
        account_reader=database_mail,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=account_id,
        decrypt_secrets=decrypt_secrets,
        missing_account_message="Mail account not found.",
        missing_external_account_id_message="Mail account is missing its external account id.",
        changed_external_account_id_message=(
            "Mail account external account id changed during runtime load."
        ),
        missing_external_account_message="Mail external account not found.",
    )
    return _coerce_mail_account_runtime(
        account=linked_account.locked_account,
        external_account=linked_account.external_account,
    )


async def load_mail_folder_runtime(
    *,
    database_mail: DatabaseMailProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    folder_id: str,
    decrypt_secrets: bool,
) -> tuple[MailAccountRuntimeState, MailFolderRuntimeState]:
    folder = await database_mail.get_folder(user_id=user_id, folder_id=folder_id)
    if folder is None:
        raise ValidationError("Mail folder not found.")
    account_id = require_folder_account_id(folder)
    runtime = await load_mail_account_runtime(
        database_mail=database_mail,
        external_accounts=external_accounts,
        user_id=user_id,
        account_id=account_id,
        decrypt_secrets=decrypt_secrets,
    )
    remote_mailbox = require_folder_remote_mailbox(folder)
    return (
        runtime,
        MailFolderRuntimeState(
            folder_id=folder_id,
            remote_mailbox=remote_mailbox,
            folder=folder,
        ),
    )


def _coerce_mail_account_runtime(
    *,
    account: JSONDict,
    external_account: JSONDict,
) -> MailAccountRuntimeState:
    account_id = coerce_trimmed_str_or_empty(account.get("id"))
    if not account_id:
        raise StateError("Mail account is missing its id.")
    inbound_host = coerce_trimmed_str_or_empty(account.get("inbound_host"))
    if not inbound_host:
        raise StateError("Mail account inbound_host is invalid.")
    smtp_host = coerce_trimmed_str_or_empty(account.get("smtp_host"))
    if not smtp_host:
        raise StateError("Mail account smtp_host is invalid.")
    inbound_port_value = account.get("inbound_port")
    if not isinstance(inbound_port_value, int):
        raise StateError("Mail account inbound_port is invalid.")
    smtp_port_value = account.get("smtp_port")
    if not isinstance(smtp_port_value, int):
        raise StateError("Mail account smtp_port is invalid.")
    inbound_security = coerce_trimmed_str_or_empty(account.get("inbound_security")).lower()
    smtp_security = coerce_trimmed_str_or_empty(account.get("smtp_security")).lower()
    protocol = require_mail_account_protocol(account)
    folder_mapping_value = account.get("folder_mapping")
    folder_mapping = folder_mapping_value if isinstance(folder_mapping_value, dict) else None
    return MailAccountRuntimeState(
        account_id=account_id,
        protocol=protocol,
        inbound_host=inbound_host,
        inbound_port=int(inbound_port_value),
        inbound_security=inbound_security,
        smtp_host=smtp_host,
        smtp_port=int(smtp_port_value),
        smtp_security=smtp_security,
        folder_mapping=folder_mapping,
        account=account,
        external_account=external_account,
    )
