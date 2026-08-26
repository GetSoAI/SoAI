"""SoAI - Mail remote search methods [backend/features/mail/mail_remote_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.errors.exceptions import StateError, ValidationError
from core.timing.formatting import timestamp_ms_to_utc_format
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int
from features.external_accounts.listing_support import resolve_limit
from features.mail.formatting import format_mail_message
from features.mail.imap_reads import run_imap_remote_search_sync
from features.mail.internal_protocols import MailRemoteSearchServiceProtocol
from features.mail.mail_cache_imports import import_folder_messages, message_identity
from features.mail.mail_record_context import (
    require_folder_account_id,
    require_folder_remote_mailbox,
)
from features.mail.transport_preparation import prepare_service_mail_transport_context

__all__ = ("remote_search_messages_method",)


async def remote_search_messages_method(
    self: MailRemoteSearchServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    arguments: JSONDict,
) -> JSONDict:
    if self.runtime_flags.offline_mode:
        raise ValidationError("Mail remote search is unavailable while offline mode is enabled.")
    async with self.account_lock(user_id=user_id, account_id=account_id):
        prepared = await prepare_service_mail_transport_context(
            self,
            user_id=user_id,
            account_id=account_id,
        )
        if prepared.runtime_state.protocol != "imap":
            raise ValidationError("Remote search is available only for IMAP accounts.")
        folder_id_value = arguments.get("folder_id")
        folder_rows = await _resolve_search_folders(
            service=self,
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id_value if isinstance(folder_id_value, str) else None,
        )
        limit = resolve_limit(
            self.config,
            arguments.get("limit"),
            "INTEGRATIONS.MAIL.REMOTE_SEARCH.LIMIT_DEFAULT",
            "INTEGRATIONS.MAIL.REMOTE_SEARCH.LIMIT_MAX",
        )
        search_criteria = _build_imap_remote_search_criteria(self, arguments)
        folder_mailboxes: list[str] = []
        for folder in folder_rows:
            folder_mailboxes.append(require_folder_remote_mailbox(folder))
        matched_payloads = await run_bounded_blocking_call(
            self.mail_blocking_pool,
            partial(
                run_imap_remote_search_sync,
                runtime_state=prepared.runtime_state,
                auth_payload=prepared.auth_payload,
                connect_timeout_sec=prepared.connect_timeout_sec,
                connect_host=prepared.inbound_connect_host,
                folder_mailboxes=folder_mailboxes,
                search_criteria=search_criteria,
                limit=limit,
                snippet_max_chars=int(
                    self.config.get_int("INTEGRATIONS.MAIL.LIMITS.SNIPPET_MAX_CHARS"),
                ),
            ),
            timeout_sec=prepared.connect_timeout_sec
            + float(self.config.get_float("INTEGRATIONS.MAIL.TIMEOUTS.COMMAND_SEC")),
        )
        folders_by_remote_mailbox: dict[str, JSONDict] = {}
        for folder in folder_rows:
            remote_mailbox = require_folder_remote_mailbox(folder)
            folders_by_remote_mailbox[remote_mailbox] = folder
        grouped_payloads: dict[str, list[JSONDict]] = {}
        for payload in matched_payloads:
            if not isinstance(payload, dict):
                raise StateError("Mail remote search payload is invalid.")
            message_value = payload.get("message")
            if not isinstance(message_value, dict):
                raise StateError("Mail remote search payload is missing its message entry.")
            remote_mailbox_value = message_value.get("remote_mailbox")
            remote_mailbox = (
                remote_mailbox_value.strip() if isinstance(remote_mailbox_value, str) else ""
            )
            if not remote_mailbox:
                raise StateError("Mail remote search payload remote_mailbox is invalid.")
            if remote_mailbox not in grouped_payloads:
                grouped_payloads[remote_mailbox] = []
            grouped_payloads[remote_mailbox].append(payload)
        imported_count = 0
        skipped_count = 0
        stored_messages_by_identity: dict[str, JSONDict] = {}
        for remote_mailbox, payloads in grouped_payloads.items():
            folder_row = folders_by_remote_mailbox.get(remote_mailbox)
            if folder_row is None:
                raise StateError("Mail remote search folder mapping is inconsistent.")
            import_result = await import_folder_messages(
                database_mail=self.database_mail,
                user_id=user_id,
                account_id=account_id,
                folder_payload=folder_row,
                message_payloads=payloads,
            )
            folder_imported_count = _read_import_count(import_result, "imported_count")
            imported_count += folder_imported_count
            updated_count = _read_import_count(import_result, "updated_count")
            skipped_count += max(
                len(payloads) - folder_imported_count - updated_count,
                0,
            )
            _add_stored_messages_by_identity(stored_messages_by_identity, import_result)
        messages: list[JSONDict] = []
        for payload in matched_payloads:
            if not isinstance(payload, dict):
                raise StateError("Mail remote search payload is invalid.")
            message_value = payload.get("message")
            if not isinstance(message_value, dict):
                raise StateError("Mail remote search payload is missing its message entry.")
            stored_message = stored_messages_by_identity.get(message_identity(message_value))
            if stored_message is None:
                raise StateError(
                    "Mail remote search cache import did not return the stored message.",
                )
            messages.append(format_mail_message(stored_message, protocol="imap"))
        return {
            "matched_count": len(matched_payloads),
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "messages": messages,
        }


async def _resolve_search_folders(
    *,
    service: MailRemoteSearchServiceProtocol,
    user_id: int,
    account_id: str,
    folder_id: str | None,
) -> list[JSONDict]:
    if isinstance(folder_id, str) and folder_id.strip():
        folder_row = await service.database_mail.get_folder(
            user_id=user_id,
            folder_id=folder_id.strip(),
        )
        if folder_row is None:
            raise ValidationError("Mail folder not found.")
        folder_account_id = require_folder_account_id(folder_row)
        if folder_account_id != account_id:
            raise ValidationError("Mail folder belongs to another account.")
        require_folder_remote_mailbox(folder_row)
        return [folder_row]
    folders = await service.database_mail.list_folders(user_id=user_id, account_id=account_id)
    if not folders:
        raise ValidationError(
            "Run mail_account_sync before remote search so folders are available.",
        )
    for folder_row in folders:
        require_folder_remote_mailbox(folder_row)
    return folders


def _build_imap_remote_search_criteria(
    service: MailRemoteSearchServiceProtocol,
    arguments: JSONDict,
) -> tuple[str, ...]:
    criteria: list[str] = ["ALL"]
    header_filters = 0
    for key, header_name in (("from", "FROM"), ("to", "TO"), ("subject", "SUBJECT")):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            criteria.extend([header_name, _imap_search_string(value)])
            header_filters += 1
    rfc822_message_id = arguments.get("rfc822_message_id")
    if isinstance(rfc822_message_id, str) and rfc822_message_id.strip():
        criteria.extend(["HEADER", "MESSAGE-ID", _imap_search_string(rfc822_message_id)])
        header_filters += 1
    has_time_bound = False
    since_ms = arguments.get("since_ms")
    if isinstance(since_ms, int):
        criteria.extend(["SINCE", _imap_date(since_ms)])
        has_time_bound = True
    before_ms = arguments.get("before_ms")
    if isinstance(before_ms, int):
        criteria.extend(["BEFORE", _imap_date(before_ms)])
        has_time_bound = True
    text_value = arguments.get("text")
    has_text = isinstance(text_value, str) and text_value.strip()
    if has_text:
        criteria.extend(["TEXT", _imap_search_string(str(text_value))])
    if bool(
        service.config.get_bool("INTEGRATIONS.MAIL.REMOTE_SEARCH.REQUIRE_NARROWING_FILTER"),
    ) and not (header_filters > 0 or has_time_bound or has_text):
        raise ValidationError("Remote search requires at least one narrowing filter.")
    if (
        has_text
        and bool(
            service.config.get_bool("INTEGRATIONS.MAIL.REMOTE_SEARCH.TEXT_REQUIRES_TIME_BOUND"),
        )
        and not has_time_bound
    ):
        raise ValidationError("text remote search requires since_ms or before_ms.")
    return tuple(criteria)


def _imap_date(timestamp_ms: int) -> str:
    return timestamp_ms_to_utc_format(timestamp_ms, "%d-%b-%Y")


def _imap_search_string(value: str) -> str:
    normalized = value.strip()
    escaped = normalized.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _read_import_count(import_result: JSONDict, key: str) -> int:
    value = import_result.get(key)
    if not is_non_negative_strict_int(value):
        raise StateError(f"{key} is invalid.")
    return value


def _add_stored_messages_by_identity(
    stored_messages_by_identity: dict[str, JSONDict],
    import_result: JSONDict,
) -> None:
    stored_messages_value = import_result.get("stored_messages")
    if not isinstance(stored_messages_value, list):
        raise StateError("stored_messages is invalid.")
    for stored_message in stored_messages_value:
        if not isinstance(stored_message, dict):
            raise StateError("stored_messages contains an invalid entry.")
        stored_messages_by_identity[message_identity(stored_message)] = stored_message
