"""SoAI - Mail outgoing message construction [backend/features/mail/outgoing_message.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.mail.outgoing_addresses import (
    apply_outgoing_recipients,
    resolve_account_address,
    resolve_message_id_domain,
)
from features.mail.outgoing_content import (
    apply_outgoing_content,
    require_choice,
    supports_draft_mode,
)

if TYPE_CHECKING:
    from core.files.database_types import FileCatalogRecordWithPath
    from core.types.json import JSONDict

__all__ = (
    "build_outgoing_message",
    "resolve_attachment_file_ids",
)


def build_outgoing_message(
    *,
    payload: JSONDict,
    username: str,
    base_message: JSONDict | None,
    base_body_text: str | None,
    attachment_records: list[FileCatalogRecordWithPath],
) -> tuple[EmailMessage, str]:
    account_address = resolve_account_address(username)
    account_email_value = account_address.get("email")
    account_email = account_email_value if isinstance(account_email_value, str) else ""
    if not account_email:
        raise ValidationError("External account username is required.")
    mode = require_choice(
        payload.get("mode"),
        label="mode",
        choices={"new", "reply", "reply_all", "forward"},
    )
    delivery = require_choice(
        payload.get("delivery"),
        label="delivery",
        choices={"send", "save_draft"},
    )
    if mode != "new" and base_message is None:
        raise ValidationError("base_message_id is required for reply and forward modes.")
    message = EmailMessage()
    message_id = make_msgid(domain=resolve_message_id_domain(account_email))
    message["Message-ID"] = message_id
    message["Date"] = formatdate(localtime=False)
    message["From"] = account_email
    apply_outgoing_recipients(
        message=message,
        mode=mode,
        payload=payload,
        base_message=base_message,
        own_email=account_email,
    )
    apply_outgoing_content(
        message=message,
        mode=mode,
        payload=payload,
        base_message=base_message,
        base_body_text=base_body_text,
        attachment_records=attachment_records,
    )
    if delivery == "save_draft" and not supports_draft_mode(payload):
        raise ValidationError("This account does not support draft delivery.")
    return message, message_id


def resolve_attachment_file_ids(payload: JSONDict) -> list[str]:
    attachments_value = payload.get("attachments")
    if attachments_value is None:
        return []
    if not isinstance(attachments_value, list):
        raise ValidationError("attachments must be a list.")
    file_ids: list[str] = []
    seen_file_ids: set[str] = set()
    for item in attachments_value:
        if not isinstance(item, dict):
            raise ValidationError("attachments items must be objects.")
        file_id_value = item.get("file_id")
        file_id = file_id_value.strip() if isinstance(file_id_value, str) else ""
        if not file_id:
            raise ValidationError("attachments items require file_id.")
        if file_id in seen_file_ids:
            continue
        seen_file_ids.add(file_id)
        file_ids.append(file_id)
    return file_ids
