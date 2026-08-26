"""SoAI - Mail cached message lookup helpers [backend/features/mail/mail_message_lookup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol
    from core.types.json import JSONDict

__all__ = (
    "find_message_id_by_message_signature",
    "find_message_id_by_rfc822_message_id",
)


async def find_message_id_by_rfc822_message_id(
    *,
    database_mail: DatabaseMailProtocol,
    user_id: int,
    folder_id: str | None,
    rfc822_message_id: str,
) -> str | None:
    if folder_id is None:
        return None
    messages = await database_mail.list_messages(user_id=user_id, folder_id=folder_id)
    for message in messages:
        message_id_value = message.get("id")
        message_id = message_id_value.strip() if isinstance(message_id_value, str) else ""
        rfc822_value = message.get("rfc822_message_id")
        if isinstance(rfc822_value, str) and rfc822_value.strip() == rfc822_message_id:
            return message_id or None
    return None


async def find_message_id_by_message_signature(
    *,
    database_mail: DatabaseMailProtocol,
    user_id: int,
    folder_id: str | None,
    message: JSONDict,
) -> str | None:
    rfc822_value = message.get("rfc822_message_id")
    if isinstance(rfc822_value, str) and rfc822_value.strip():
        matched = await find_message_id_by_rfc822_message_id(
            database_mail=database_mail,
            user_id=user_id,
            folder_id=folder_id,
            rfc822_message_id=rfc822_value.strip(),
        )
        if matched is not None:
            return matched
    if folder_id is None:
        return None
    messages = await database_mail.list_messages(user_id=user_id, folder_id=folder_id)
    thread_id_value = message.get("thread_id")
    subject_value = message.get("subject")
    size_value = message.get("size_bytes")
    sent_at_value = message.get("sent_at_ms")
    received_at_value = message.get("received_at_ms")
    for candidate in messages:
        if candidate.get("thread_id") != thread_id_value:
            continue
        if candidate.get("subject") != subject_value:
            continue
        if candidate.get("size_bytes") != size_value:
            continue
        if candidate.get("sent_at_ms") != sent_at_value:
            continue
        if candidate.get("received_at_ms") != received_at_value:
            continue
        message_id_value = candidate.get("id")
        if isinstance(message_id_value, str) and message_id_value.strip():
            return message_id_value.strip()
    return None
