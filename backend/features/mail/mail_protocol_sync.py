"""SoAI - Mail protocol-specific sync helpers [backend/features/mail/mail_protocol_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.errors.exceptions import StateError
from core.validation.integers import is_non_negative_strict_int
from features.mail.imap_reads import run_imap_sync_snapshot_sync
from features.mail.mail_sync_notifications import resolve_mail_account_label
from features.mail.pop3_reads import run_pop3_sync_snapshot_sync

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.mail.protocols import DatabaseMailProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "sync_imap_mail_account",
    "sync_pop3_mail_account",
)


async def sync_imap_mail_account(
    *,
    config: ConfigProtocol,
    database_mail: DatabaseMailProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    mail_blocking_pool: BoundedBlockingPool,
    user_id: int,
    account_id: str,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    target_remote_mailbox: str | None,
    prior_sync_exists: bool,
    import_folder_messages: Callable[..., Awaitable[JSONDict]],
) -> JSONDict:
    include_names = _read_name_list(config, "INTEGRATIONS.MAIL.SYNC.FOLDERS.INCLUDE_NAMES")
    exclude_names = _read_name_list(config, "INTEGRATIONS.MAIL.SYNC.FOLDERS.EXCLUDE_NAMES")
    snapshot = await run_bounded_blocking_call(
        mail_blocking_pool,
        partial(
            run_imap_sync_snapshot_sync,
            runtime_state=runtime_state,
            auth_payload=auth_payload,
            connect_timeout_sec=connect_timeout_sec,
            connect_host=connect_host,
            history_max_age_days=int(config.get_int("INTEGRATIONS.MAIL.SYNC.HISTORY.MAX_AGE_DAYS")),
            max_messages_per_folder=int(
                config.get_int("INTEGRATIONS.MAIL.SYNC.HISTORY.MAX_MESSAGES_PER_FOLDER"),
            ),
            target_remote_mailbox=target_remote_mailbox,
            include_special_use=bool(
                config.get_bool("INTEGRATIONS.MAIL.SYNC.FOLDERS.INCLUDE_SPECIAL_USE"),
            ),
            include_names=include_names,
            exclude_names=exclude_names,
            snippet_max_chars=int(config.get_int("INTEGRATIONS.MAIL.LIMITS.SNIPPET_MAX_CHARS")),
        ),
        timeout_sec=connect_timeout_sec
        + float(config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    folders_value = snapshot.get("folders")
    if not isinstance(folders_value, list):
        raise StateError("IMAP sync snapshot folders is invalid.")
    folders = folders_value
    messages_by_mailbox_value = snapshot.get("messages_by_mailbox")
    if not isinstance(messages_by_mailbox_value, dict):
        raise StateError("IMAP sync snapshot messages_by_mailbox is invalid.")
    messages_by_mailbox = messages_by_mailbox_value
    listed_folders_value = snapshot.get("listed_folders")
    if not isinstance(listed_folders_value, list):
        raise StateError("IMAP sync snapshot listed_folders is invalid.")
    listed_folders = listed_folders_value
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    warnings: list[str] = []
    validated_folders: list[JSONDict] = []
    validated_listed_folders: list[JSONDict] = []
    for listed_folder in listed_folders:
        if not isinstance(listed_folder, dict):
            raise StateError("IMAP sync snapshot listed folder entry is invalid.")
        validated_listed_folders.append(listed_folder)
        await database_mail.upsert_folder(
            user_id=user_id,
            account_id=account_id,
            payload=listed_folder,
        )
    for folder_payload in folders:
        if not isinstance(folder_payload, dict):
            raise StateError("IMAP sync snapshot folder entry is invalid.")
        validated_folders.append(folder_payload)
        remote_mailbox_value = folder_payload.get("remote_mailbox")
        remote_mailbox = remote_mailbox_value if isinstance(remote_mailbox_value, str) else ""
        if not remote_mailbox.strip():
            raise StateError("IMAP sync snapshot folder remote_mailbox is invalid.")
        message_payloads_value = messages_by_mailbox.get(remote_mailbox)
        if not isinstance(message_payloads_value, list):
            raise StateError("IMAP sync snapshot folder message payloads is invalid.")
        message_payloads = message_payloads_value
        folder_counts = await import_folder_messages(
            database_mail=database_mail,
            database_notifications=database_notifications,
            user_id=user_id,
            account_id=account_id,
            folder_payload=folder_payload,
            message_payloads=message_payloads,
            prune_missing_messages=True,
            prior_sync_exists=prior_sync_exists,
            account_label=resolve_mail_account_label(
                runtime_state.account,
                runtime_state.external_account,
            ),
        )
        imported_count += _read_import_count(folder_counts, "imported_count")
        updated_count += _read_import_count(folder_counts, "updated_count")
        skipped_count += _read_import_count(folder_counts, "skipped_count")
        _extend_warnings(warnings, folder_counts)
    if target_remote_mailbox is None:
        await _delete_missing_cached_folders(
            database_mail=database_mail,
            user_id=user_id,
            account_id=account_id,
            listed_folders=validated_listed_folders,
        )
    result: JSONDict = {
        "account_id": account_id,
        "synced_folders_count": len(folders),
        "imported_count": imported_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
    }
    if warnings:
        result["warnings"] = warnings
    return result


async def sync_pop3_mail_account(
    *,
    config: ConfigProtocol,
    database_mail: DatabaseMailProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    mail_blocking_pool: BoundedBlockingPool,
    user_id: int,
    account_id: str,
    runtime_state: MailAccountRuntimeState,
    auth_payload: JSONDict,
    connect_timeout_sec: float,
    connect_host: str,
    prior_sync_exists: bool,
    import_folder_messages: Callable[..., Awaitable[JSONDict]],
) -> JSONDict:
    snapshot = await run_bounded_blocking_call(
        mail_blocking_pool,
        partial(
            run_pop3_sync_snapshot_sync,
            runtime_state=runtime_state,
            auth_payload=auth_payload,
            connect_timeout_sec=connect_timeout_sec,
            connect_host=connect_host,
            max_messages_per_folder=int(
                config.get_int("INTEGRATIONS.MAIL.SYNC.HISTORY.MAX_MESSAGES_PER_FOLDER"),
            ),
            snippet_max_chars=int(config.get_int("INTEGRATIONS.MAIL.LIMITS.SNIPPET_MAX_CHARS")),
        ),
        timeout_sec=connect_timeout_sec
        + float(config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
    )
    folder_payload_value = snapshot.get("folder")
    if not isinstance(folder_payload_value, dict):
        raise StateError("POP3 sync snapshot folder is invalid.")
    folder_payload = folder_payload_value
    message_payloads_value = snapshot.get("messages")
    if not isinstance(message_payloads_value, list):
        raise StateError("POP3 sync snapshot messages is invalid.")
    message_payloads = message_payloads_value
    folder_counts = await import_folder_messages(
        database_mail=database_mail,
        database_notifications=database_notifications,
        user_id=user_id,
        account_id=account_id,
        folder_payload=folder_payload,
        message_payloads=message_payloads,
        prior_sync_exists=prior_sync_exists,
        account_label=resolve_mail_account_label(
            runtime_state.account,
            runtime_state.external_account,
        ),
    )
    result: JSONDict = {
        "account_id": account_id,
        "synced_folders_count": 1,
        "imported_count": _read_import_count(folder_counts, "imported_count"),
        "updated_count": _read_import_count(folder_counts, "updated_count"),
        "skipped_count": _read_import_count(folder_counts, "skipped_count"),
    }
    warnings: list[str] = []
    _extend_warnings(warnings, folder_counts)
    if warnings:
        result["warnings"] = warnings
    return result


def _read_name_list(config: ConfigProtocol, key: str) -> list[str]:
    raw_value = config.get(key, [])
    if not isinstance(raw_value, list):
        return []
    return [item.strip() for item in raw_value if isinstance(item, str) and item.strip()]


def _read_import_count(folder_counts: JSONDict, key: str) -> int:
    value = folder_counts.get(key)
    if not is_non_negative_strict_int(value):
        raise StateError(f"{key} is invalid.")
    return value


def _extend_warnings(warnings: list[str], folder_counts: JSONDict) -> None:
    warnings_value = folder_counts.get("warnings")
    if not isinstance(warnings_value, list):
        return
    for warning in warnings_value:
        if isinstance(warning, str) and warning:
            warnings.append(warning)


async def _delete_missing_cached_folders(
    *,
    database_mail: DatabaseMailProtocol,
    user_id: int,
    account_id: str,
    listed_folders: list[JSONDict],
) -> None:
    observed_remote_mailboxes: set[str] = set()
    for listed_folder in listed_folders:
        remote_mailbox_value = listed_folder.get("remote_mailbox")
        remote_mailbox = (
            remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
        )
        if not remote_mailbox:
            raise StateError("IMAP sync snapshot listed folder remote_mailbox is invalid.")
        observed_remote_mailboxes.add(remote_mailbox)
    cached_folders = await database_mail.list_folders(user_id=user_id, account_id=account_id)
    for cached_folder in cached_folders:
        remote_mailbox_value = cached_folder.get("remote_mailbox")
        remote_mailbox = (
            remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
        )
        if not remote_mailbox:
            raise StateError("Mail folder cache entry remote_mailbox is invalid.")
        if remote_mailbox in observed_remote_mailboxes:
            continue
        folder_id_value = cached_folder.get("id")
        folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else ""
        if not folder_id:
            raise StateError("Mail folder cache entry is missing its id.")
        await database_mail.delete_folder(user_id=user_id, folder_id=folder_id)
