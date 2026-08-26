"""SoAI - Mail cache import helpers [backend/features/mail/mail_cache_imports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_json_object, require_json_object_list

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol
    from core.types.json import JSONDict

__all__ = (
    "import_folder_messages",
    "message_identity",
)


async def import_folder_messages(
    *,
    database_mail: DatabaseMailProtocol,
    user_id: int,
    account_id: str,
    folder_payload: JSONDict,
    message_payloads: list[JSONDict],
    prune_missing_messages: bool = False,
) -> JSONDict:
    folder_row = await database_mail.upsert_folder(
        user_id=user_id,
        account_id=account_id,
        payload=folder_payload,
    )
    folder_id_value = folder_row.get("id")
    folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else ""
    if not folder_id:
        raise StateError("Mail folder cache entry is missing its id.")
    existing_messages = await database_mail.list_messages(user_id=user_id, folder_id=folder_id)
    known_identities = {message_identity(item) for item in existing_messages}
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    imported_messages: list[JSONDict] = []
    stored_messages: list[JSONDict] = []
    observed_identities: set[str] = set()
    for payload in message_payloads:
        payload_object = require_json_object(
            payload,
            label="Mail message payload",
            build_error=StateError,
            invalid_message="Mail message payload is invalid.",
        )
        message_value = require_json_object(
            payload_object.get("message"),
            label="Mail message payload message",
            build_error=StateError,
            invalid_message="Mail message payload is missing its message entry.",
        )
        identity = message_identity(message_value)
        observed_identities.add(identity)
        created = identity not in known_identities
        stored_message = await database_mail.upsert_message(
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id,
            payload=message_value,
        )
        stored_messages.append(stored_message)
        body_text_value = payload_object.get("body_text")
        if not isinstance(body_text_value, str):
            raise StateError("Mail message payload body_text is invalid.")
        body_text = body_text_value
        body_html_value = payload_object.get("body_html")
        if body_html_value is None:
            body_html = None
        elif isinstance(body_html_value, str) and body_html_value.strip():
            body_html = body_html_value
        else:
            raise StateError("Mail message payload body_html is invalid.")
        parts = require_json_object_list(
            payload_object.get("parts"),
            label="Mail message payload parts",
            build_error=StateError,
            invalid_message="Mail message payload parts is invalid.",
            entry_message="Mail message payload parts contains invalid entries.",
        )
        stored_message_id_value = stored_message.get("id")
        stored_message_id = (
            stored_message_id_value.strip() if isinstance(stored_message_id_value, str) else ""
        )
        if not stored_message_id:
            raise StateError("Mail cache message entry is missing its id.")
        await database_mail.replace_message_body(
            user_id=user_id,
            message_id=stored_message_id,
            body_text=body_text,
            body_html=body_html,
            total_chars=len(body_text),
            parts=parts,
        )
        if created:
            imported_count += 1
            known_identities.add(identity)
            imported_messages.append(stored_message)
            continue
        updated_count += 1
    if prune_missing_messages:
        missing_message_ids: list[str] = []
        for existing_message in existing_messages:
            if message_identity(existing_message) in observed_identities:
                continue
            message_id_value = existing_message.get("id")
            message_id = message_id_value.strip() if isinstance(message_id_value, str) else ""
            if message_id:
                missing_message_ids.append(message_id)
        if missing_message_ids:
            await database_mail.delete_messages(
                user_id=user_id,
                folder_id=folder_id,
                message_ids=missing_message_ids,
            )
    return {
        "folder": folder_row,
        "imported_count": imported_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "imported_messages": imported_messages,
        "stored_messages": stored_messages,
    }


def message_identity(message: JSONDict) -> str:
    uidl_value = message.get("uidl")
    if uidl_value is not None:
        if not isinstance(uidl_value, str) or not uidl_value.strip():
            raise StateError("Mail message uidl is invalid.")
        return f"pop3:{uidl_value.strip()}"
    remote_mailbox_value = message.get("remote_mailbox")
    uidvalidity_value = message.get("uidvalidity")
    uid_value = message.get("uid")
    if not isinstance(remote_mailbox_value, str) or not remote_mailbox_value.strip():
        raise StateError("Mail message remote_mailbox is invalid.")
    remote_mailbox = remote_mailbox_value.strip()
    if (
        isinstance(uidvalidity_value, bool)
        or not isinstance(uidvalidity_value, int)
        or uidvalidity_value < 1
    ):
        raise StateError("Mail message uidvalidity is invalid.")
    uidvalidity = uidvalidity_value
    if not is_strict_int(uid_value) or uid_value < 1:
        raise StateError("Mail message uid is invalid.")
    uid = uid_value
    return f"imap:{remote_mailbox}:{uidvalidity}:{uid}"
