"""SoAI - Mail message repository row builders [backend/database/repositories/users/mail/message_row_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    optional_mail_folder_id,
    require_mail_folder_id,
)
from core.validation.strings import coerce_optional_trimmed_str
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.account_validation import (
    optional_epoch_ms,
    optional_json_list,
    optional_json_object,
    require_bool_int,
    require_nonnegative_int,
    require_text,
)
from database.repositories.users.mail.validation import require_json_list

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "MailMessageIdentity",
    "build_message_row",
    "build_message_updates",
    "resolve_message_identity",
)


@dataclass(frozen=True, slots=True)
class MailMessageIdentity:
    protocol: str
    remote_mailbox: str | None
    uidvalidity: int | None
    uid: int | None
    uidl: str | None


def resolve_message_identity(payload: JSONDict) -> MailMessageIdentity:
    uidl = coerce_optional_trimmed_str(payload.get("uidl"))
    if uidl is not None:
        return MailMessageIdentity(
            protocol="pop3",
            remote_mailbox=None,
            uidvalidity=None,
            uid=None,
            uidl=uidl,
        )
    return MailMessageIdentity(
        protocol="imap",
        remote_mailbox=require_text(payload.get("remote_mailbox"), "remote_mailbox"),
        uidvalidity=require_nonnegative_int(payload.get("uidvalidity"), "uidvalidity"),
        uid=require_nonnegative_int(payload.get("uid"), "uid"),
        uidl=None,
    )


def build_message_row(
    *,
    user_id: int,
    account_id: str,
    folder_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    now_ms = (
        optional_epoch_ms(payload.get("last_modified_at_ms"), label="last_modified_at_ms")
        or epoch_ms()
    )
    uidl = coerce_optional_trimmed_str(payload.get("uidl"))
    uidvalidity = (
        None
        if uidl is not None
        else require_nonnegative_int(payload.get("uidvalidity"), "uidvalidity")
    )
    uid = None if uidl is not None else require_nonnegative_int(payload.get("uid"), "uid")
    return {
        "user_id": user_id,
        "mail_account_id": account_id,
        "folder_id": require_mail_folder_id(folder_id),
        "remote_mailbox": coerce_optional_trimmed_str(payload.get("remote_mailbox")),
        "uidvalidity": uidvalidity,
        "uid": uid,
        "uidl": uidl,
        "thread_id": require_text(payload.get("thread_id"), "thread_id"),
        "rfc822_message_id": coerce_optional_trimmed_str(payload.get("rfc822_message_id")),
        "in_reply_to_message_id": coerce_optional_trimmed_str(
            payload.get("in_reply_to_message_id"),
        ),
        "references_json": optional_json_list(payload.get("references")),
        "subject": require_text(payload.get("subject"), "subject"),
        "from_json": require_json_list(payload.get("from"), "from"),
        "to_json": require_json_list(payload.get("to"), "to"),
        "cc_json": optional_json_list(payload.get("cc")),
        "bcc_json": optional_json_list(payload.get("bcc")),
        "sent_at_ms": optional_epoch_ms(payload.get("sent_at_ms"), label="sent_at_ms"),
        "received_at_ms": require_nonnegative_int(payload.get("received_at_ms"), "received_at_ms"),
        "snippet": require_text(payload.get("snippet"), "snippet"),
        "size_bytes": require_nonnegative_int(payload.get("size_bytes"), "size_bytes"),
        "unread": require_bool_int(payload.get("unread"), "unread"),
        "flagged": require_bool_int(payload.get("flagged"), "flagged"),
        "has_attachments": require_bool_int(payload.get("has_attachments"), "has_attachments"),
        "attachment_count": require_nonnegative_int(
            payload.get("attachment_count"),
            "attachment_count",
        ),
        "deleted_original_folder_id": optional_mail_folder_id(
            payload.get("deleted_original_folder_id"),
        ),
        "invite_json": optional_json_object(payload.get("invite")),
        "created_at_ms": optional_epoch_ms(payload.get("created_at_ms"), label="created_at_ms")
        or now_ms,
        "last_modified_at_ms": now_ms,
    }


def build_message_updates(updates: JSONDict) -> dict[str, SQLiteValue]:
    mapped: dict[str, SQLiteValue] = {"last_modified_at_ms": epoch_ms()}
    for key, value in updates.items():
        if key == "folder_id":
            mapped["folder_id"] = require_mail_folder_id(require_text(value, "folder_id"))
        elif key == "subject":
            mapped["subject"] = require_text(value, "subject")
        elif key == "snippet":
            mapped["snippet"] = require_text(value, "snippet")
        elif key == "unread":
            mapped["unread"] = require_bool_int(value, "unread")
        elif key == "flagged":
            mapped["flagged"] = require_bool_int(value, "flagged")
        elif key == "has_attachments":
            mapped["has_attachments"] = require_bool_int(value, "has_attachments")
        elif key == "attachment_count":
            mapped["attachment_count"] = require_nonnegative_int(value, "attachment_count")
        elif key == "deleted_original_folder_id":
            mapped["deleted_original_folder_id"] = optional_mail_folder_id(value)
        elif key == "invite":
            mapped["invite_json"] = optional_json_object(value)
    return mapped
