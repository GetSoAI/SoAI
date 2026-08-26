"""SoAI - Mail record loading and relationship validation [backend/features/mail/mail_record_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.validation.strings import coerce_trimmed_str_or_empty
from features.mail.mail_account_context import require_mail_account_protocol

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol
    from core.types.json import JSONDict

__all__ = (
    "LoadedMailFolderContext",
    "load_folder_context",
    "require_folder_account_id",
    "require_folder_remote_mailbox",
    "require_message_account_id",
    "require_remote_mailbox",
)


@dataclass(frozen=True, slots=True)
class LoadedMailFolderContext:
    folder: JSONDict
    account: JSONDict
    account_id: str
    protocol: str


async def load_folder_context(
    database_mail: DatabaseMailProtocol,
    *,
    user_id: int,
    folder_id: str,
    missing_error: type[Exception] = ValidationError,
    missing_message: str = "Mail folder not found.",
) -> LoadedMailFolderContext:
    folder = await database_mail.get_folder(user_id=user_id, folder_id=folder_id)
    if folder is None:
        raise missing_error(missing_message)
    account_id = require_folder_account_id(folder)
    account = await database_mail.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        raise StateError("Mail account not found.")
    return LoadedMailFolderContext(
        folder=folder,
        account=account,
        account_id=account_id,
        protocol=require_mail_account_protocol(account),
    )


def require_folder_account_id(folder: JSONDict) -> str:
    account_id = coerce_trimmed_str_or_empty(folder.get("mail_account_id"))
    if not account_id:
        raise StateError("Mail folder is missing its account id.")
    return account_id


def require_message_account_id(message: JSONDict) -> str:
    account_id = coerce_trimmed_str_or_empty(message.get("mail_account_id"))
    if not account_id:
        raise StateError("Mail message is missing its account id.")
    return account_id


def require_folder_remote_mailbox(folder: JSONDict) -> str:
    return require_remote_mailbox(
        folder,
        message="Mail folder is missing its remote mailbox.",
    )


def require_remote_mailbox(folder_or_message: JSONDict, *, message: str) -> str:
    remote_mailbox = coerce_trimmed_str_or_empty(folder_or_message.get("remote_mailbox"))
    if not remote_mailbox:
        raise StateError(message)
    return remote_mailbox
