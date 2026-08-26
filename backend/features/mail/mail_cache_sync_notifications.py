"""SoAI - Mail cache sync notification helpers [backend/features/mail/mail_cache_sync_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int
from features.mail.mail_cache_imports import import_folder_messages
from features.mail.mail_sync_notifications import (
    create_mail_new_message_notification,
    resolve_mail_account_label,
    resolve_mail_sender_label,
    resolve_mail_subject,
)

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from features.mail.internal_protocols import MailCacheSyncServiceProtocol
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = (
    "resolve_mail_sync_failure_label",
    "upsert_folder_messages_with_notifications",
)

OPERATION = "features.mail.mail_cache_sync"
LOGGER_NAME = "SoAI.features.mail.mail_cache_sync_notifications"


async def upsert_folder_messages_with_notifications(
    *,
    database_mail: DatabaseMailProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_id: str,
    folder_payload: JSONDict,
    message_payloads: list[JSONDict],
    prune_missing_messages: bool,
    prior_sync_exists: bool,
    account_label: str,
) -> JSONDict:
    warnings: list[str] = []
    import_result = await import_folder_messages(
        database_mail=database_mail,
        user_id=user_id,
        account_id=account_id,
        folder_payload=folder_payload,
        message_payloads=message_payloads,
        prune_missing_messages=prune_missing_messages,
    )
    if prior_sync_exists:
        imported_messages_value = import_result.get("imported_messages")
        if not isinstance(imported_messages_value, list):
            raise StateError("Mail cache import result imported_messages is invalid.")
        imported_messages = imported_messages_value
        for stored_message in imported_messages:
            try:
                if not isinstance(stored_message, dict):
                    raise StateError("Mail cache import result imported_message entry is invalid.")
                unread = _read_unread_flag(stored_message)
                if unread is False:
                    continue
                if unread is not True:
                    raise StateError("Mail cache imported message unread flag is invalid.")
                await create_mail_new_message_notification(
                    database_notifications=database_notifications,
                    user_id=user_id,
                    account_label=account_label,
                    from_label=resolve_mail_sender_label(stored_message),
                    subject=resolve_mail_subject(stored_message),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    _mail_cache_sync_notifications_logger(),
                    exception,
                    message="Failed to create new message notification during mail sync.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id, "account_id": account_id},
                )
                warning_reason = project_public_exception(exception).message
                warnings.append(
                    f"Mail sync imported a new message, but SoAI could not create its notification: {warning_reason}",
                )
    result: JSONDict = {
        "imported_count": _read_import_count(import_result, "imported_count"),
        "updated_count": _read_import_count(import_result, "updated_count"),
        "skipped_count": _read_import_count(import_result, "skipped_count"),
    }
    if warnings:
        result["warnings"] = warnings
    return result


async def resolve_mail_sync_failure_label(
    *,
    service: MailCacheSyncServiceProtocol,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext | None,
) -> str:
    if prepared is not None:
        return resolve_mail_account_label(
            prepared.runtime_state.account,
            prepared.runtime_state.external_account,
        )
    account = await service.database_mail.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        return account_id
    external_account_id_value = account.get("external_account_id")
    external_account_id = (
        external_account_id_value.strip() if isinstance(external_account_id_value, str) else ""
    )
    external_account: JSONDict = {}
    if external_account_id:
        loaded_external_account = await service.external_accounts.get_account(
            user_id,
            external_account_id,
            decrypt_secrets=False,
        )
        if loaded_external_account is not None:
            external_account = loaded_external_account
    return resolve_mail_account_label(account, external_account)


def _read_import_count(import_result: JSONDict, key: str) -> int:
    value = import_result.get(key)
    if not is_non_negative_strict_int(value):
        raise StateError(f"Mail cache import result {key} is invalid.")
    return value


def _read_unread_flag(message: JSONDict) -> bool | None:
    value = message.get("unread")
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return value == 1
    return None


def _mail_cache_sync_notifications_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
