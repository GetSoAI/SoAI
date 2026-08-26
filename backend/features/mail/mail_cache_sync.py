"""SoAI - Mail cache sync operations [backend/features/mail/mail_cache_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.messages import resolve_exception_error_message
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.external_accounts.sync_error_dedup import resolve_previous_sync_error
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from features.mail.internal_protocols import MailCacheSyncServiceProtocol
from features.mail.mail_cache_sync_notifications import (
    resolve_mail_sync_failure_label,
    upsert_folder_messages_with_notifications,
)
from features.mail.mail_protocol_sync import (
    sync_imap_mail_account,
    sync_pop3_mail_account,
)
from features.mail.mail_sync_notifications import (
    create_mail_sync_failure_notification,
)
from features.mail.runtime_state import load_mail_folder_runtime
from features.mail.transport_preparation import prepare_service_mail_transport_context

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.mail.transport_context import PreparedMailTransportContext

__all__ = ("sync_mail_account_cache",)

OPERATION = "features.mail.mail_cache_sync"
LOGGER_NAME = "SoAI.features.mail.mail_cache_sync"


async def sync_mail_account_cache(
    service: MailCacheSyncServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    folder_id: str | None,
    target_remote_mailbox: str | None = None,
) -> JSONDict:
    if service.runtime_flags.offline_mode:
        raise ValidationError("Mail sync is unavailable while offline mode is enabled.")
    async with service.account_lock(user_id=user_id, account_id=account_id):
        sync_started_at_ms = epoch_ms()
        prepared: PreparedMailTransportContext | None = None
        try:
            prepared = await prepare_service_mail_transport_context(
                service,
                user_id=user_id,
                account_id=account_id,
            )
            if folder_id is not None:
                folder_runtime_state, folder_runtime = await load_mail_folder_runtime(
                    database_mail=service.database_mail,
                    external_accounts=service.external_accounts,
                    user_id=user_id,
                    folder_id=folder_id,
                    decrypt_secrets=False,
                )
                if folder_runtime_state.account_id != account_id:
                    raise ValidationError("Mail folder belongs to another account.")
                if target_remote_mailbox is None:
                    target_remote_mailbox = folder_runtime.remote_mailbox
                elif folder_runtime.remote_mailbox != target_remote_mailbox:
                    raise StateError(
                        "Mail folder remote mailbox does not match the requested target.",
                    )
            prior_sync_exists = isinstance(
                prepared.runtime_state.account.get("last_sync_at_ms"),
                int,
            )
            if prepared.runtime_state.protocol == "imap":
                result = await sync_imap_mail_account(
                    config=service.config,
                    database_mail=service.database_mail,
                    database_notifications=service.database_notifications,
                    mail_blocking_pool=service.mail_blocking_pool,
                    user_id=user_id,
                    account_id=account_id,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    target_remote_mailbox=target_remote_mailbox,
                    prior_sync_exists=prior_sync_exists,
                    import_folder_messages=upsert_folder_messages_with_notifications,
                )
            else:
                result = await sync_pop3_mail_account(
                    config=service.config,
                    database_mail=service.database_mail,
                    database_notifications=service.database_notifications,
                    mail_blocking_pool=service.mail_blocking_pool,
                    user_id=user_id,
                    account_id=account_id,
                    runtime_state=prepared.runtime_state,
                    auth_payload=prepared.auth_payload,
                    connect_timeout_sec=prepared.connect_timeout_sec,
                    connect_host=prepared.inbound_connect_host,
                    prior_sync_exists=prior_sync_exists,
                    import_folder_messages=upsert_folder_messages_with_notifications,
                )
            try:
                await service.database_mail.update_account(
                    user_id=user_id,
                    account_id=account_id,
                    updates={
                        "last_sync_at_ms": sync_started_at_ms,
                        "last_sync_error": None,
                    },
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    _mail_cache_sync_logger(),
                    exception,
                    message="Failed to persist mail sync metadata after successful sync.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id, "account_id": account_id},
                )
                warning_reason = project_public_exception(exception).message
                _append_warning(
                    result,
                    f"Mail sync completed, but SoAI could not persist the sync metadata: {warning_reason}",
                )
            result["last_sync_at_ms"] = sync_started_at_ms
            result["last_sync_error"] = None
            return result
        except RECOVERABLE_EXCEPTIONS as exception:
            error_message = project_public_exception(exception).message
            previous_error = await _resolve_previous_sync_error(
                service=service,
                user_id=user_id,
                account_id=account_id,
                prepared=prepared,
            )
            try:
                await service.database_mail.update_account(
                    user_id=user_id,
                    account_id=account_id,
                    updates={
                        "last_sync_error": error_message,
                    },
                )
            except RECOVERABLE_EXCEPTIONS as status_exception:
                log_exception(
                    _mail_cache_sync_logger(),
                    status_exception,
                    message="Failed to persist mail sync failure metadata.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id, "account_id": account_id},
                )
                status_reason = resolve_exception_error_message(status_exception)
                exception.add_note(
                    f"Also failed to persist the mail sync failure metadata: {status_reason}",
                )
            try:
                if previous_error != error_message:
                    await create_mail_sync_failure_notification(
                        database_notifications=service.database_notifications,
                        user_id=user_id,
                        account_label=await resolve_mail_sync_failure_label(
                            service=service,
                            user_id=user_id,
                            account_id=account_id,
                            prepared=prepared,
                        ),
                        reason=error_message,
                    )
            except RECOVERABLE_EXCEPTIONS as notification_exception:
                log_exception(
                    _mail_cache_sync_logger(),
                    notification_exception,
                    message="Failed to create mail sync failure notification.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id, "account_id": account_id},
                )
                notification_reason = resolve_exception_error_message(notification_exception)
                exception.add_note(
                    f"Also failed to create the mail sync failure notification: {notification_reason}",
                )
            raise


def _append_warning(result: JSONDict, warning: str) -> None:
    warnings_value = result.get("warnings")
    warnings = warnings_value if isinstance(warnings_value, list) else []
    warnings.append(warning)
    result["warnings"] = warnings


def _mail_cache_sync_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)


async def _resolve_previous_sync_error(
    *,
    service: MailCacheSyncServiceProtocol,
    user_id: int,
    account_id: str,
    prepared: PreparedMailTransportContext | None,
) -> str | None:
    return await resolve_previous_sync_error(
        prepared_account=prepared.runtime_state.account if prepared is not None else None,
        fetch_account=lambda: service.database_mail.get_account(
            user_id=user_id,
            account_id=account_id,
        ),
        logger=_mail_cache_sync_logger(),
        operation=OPERATION,
        sync_label="mail",
        details={"user_id": user_id, "account_id": account_id},
    )
