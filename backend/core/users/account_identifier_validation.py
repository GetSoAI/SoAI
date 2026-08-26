"""SoAI - User account identifier validation helpers [backend/core/users/account_identifier_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.users.account_identifiers import (
    CALENDAR_ACCOUNT_ID_PREFIX,
    CALENDAR_CALENDAR_ID_PREFIX,
    CALENDAR_EVENT_ID_PREFIX,
    CALENDAR_REMINDER_ID_PREFIX,
    EXTERNAL_ACCOUNT_ID_PREFIX,
    MAIL_ACCOUNT_ID_PREFIX,
    MAIL_ATTACHMENT_ID_PREFIX,
    MAIL_FOLDER_ID_PREFIX,
    MAIL_MESSAGE_ID_PREFIX,
)
from core.validation.identifiers import (
    optional_prefixed_identifier,
    require_prefixed_identifier,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "optional_linked_mail_account_id",
    "optional_mail_attachment_id",
    "optional_mail_folder_id",
    "require_calendar_account_id",
    "require_calendar_calendar_id",
    "require_calendar_event_id",
    "require_calendar_reminder_id",
    "require_external_account_id",
    "require_mail_account_id",
    "require_mail_attachment_id",
    "require_mail_folder_id",
    "require_mail_message_id",
)


def require_external_account_id(external_account_id: str) -> str:
    return require_prefixed_identifier(
        external_account_id,
        prefix=EXTERNAL_ACCOUNT_ID_PREFIX,
        label="external_account_id",
    )


def require_mail_account_id(account_id: str) -> str:
    return require_prefixed_identifier(
        account_id,
        prefix=MAIL_ACCOUNT_ID_PREFIX,
        label="account_id",
    )


def require_mail_folder_id(folder_id: str) -> str:
    return require_prefixed_identifier(
        folder_id,
        prefix=MAIL_FOLDER_ID_PREFIX,
        label="folder_id",
    )


def optional_mail_folder_id(value: JSONValue | str | None) -> str | None:
    return optional_prefixed_identifier(value, prefix=MAIL_FOLDER_ID_PREFIX, label="folder_id")


def require_mail_message_id(message_id: str) -> str:
    return require_prefixed_identifier(
        message_id,
        prefix=MAIL_MESSAGE_ID_PREFIX,
        label="message_id",
    )


def require_mail_attachment_id(attachment_id: str) -> str:
    return require_prefixed_identifier(
        attachment_id,
        prefix=MAIL_ATTACHMENT_ID_PREFIX,
        label="attachment_id",
    )


def optional_mail_attachment_id(value: JSONValue | str | None) -> str | None:
    return optional_prefixed_identifier(
        value,
        prefix=MAIL_ATTACHMENT_ID_PREFIX,
        label="attachment_id",
    )


def require_calendar_account_id(account_id: str) -> str:
    return require_prefixed_identifier(
        account_id,
        prefix=CALENDAR_ACCOUNT_ID_PREFIX,
        label="account_id",
    )


def optional_linked_mail_account_id(value: JSONValue | str | None) -> str | None:
    return optional_prefixed_identifier(
        value,
        prefix=MAIL_ACCOUNT_ID_PREFIX,
        label="linked_mail_account_id",
    )


def require_calendar_calendar_id(calendar_id: str) -> str:
    return require_prefixed_identifier(
        calendar_id,
        prefix=CALENDAR_CALENDAR_ID_PREFIX,
        label="calendar_id",
    )


def require_calendar_event_id(event_id: str) -> str:
    return require_prefixed_identifier(
        event_id,
        prefix=CALENDAR_EVENT_ID_PREFIX,
        label="event_id",
    )


def require_calendar_reminder_id(reminder_id: str) -> str:
    return require_prefixed_identifier(
        reminder_id,
        prefix=CALENDAR_REMINDER_ID_PREFIX,
        label="reminder_id",
    )
