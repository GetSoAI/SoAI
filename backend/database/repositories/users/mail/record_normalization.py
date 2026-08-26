"""SoAI - Mail repository row normalization [backend/database/repositories/users/mail/record_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from database.core.json_codec import (
    parse_optional_json_list_field,
    parse_optional_json_object_field,
)
from database.core.row_booleans import normalize_bool_field
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "normalize_mail_account_row",
    "normalize_mail_body_row",
    "normalize_mail_folder_row",
    "normalize_mail_message_row",
    "normalize_mail_part_row",
)


def normalize_mail_account_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["folder_mapping"] = parse_optional_json_object_field(
        formatted.get("folder_mapping_json"),
    )
    formatted.pop("folder_mapping_json", None)
    return formatted


def normalize_mail_folder_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    normalize_bool_field(formatted, "subscribed")
    return formatted


def normalize_mail_message_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["from"] = parse_optional_json_list_field(formatted.get("from_json"))
    formatted["to"] = parse_optional_json_list_field(formatted.get("to_json"))
    formatted["cc"] = parse_optional_json_list_field(formatted.get("cc_json"))
    formatted["bcc"] = parse_optional_json_list_field(formatted.get("bcc_json"))
    formatted["references"] = parse_optional_json_list_field(formatted.get("references_json"))
    formatted["invite"] = parse_optional_json_object_field(formatted.get("invite_json"))
    for key in (
        "from_json",
        "to_json",
        "cc_json",
        "bcc_json",
        "references_json",
        "invite_json",
    ):
        formatted.pop(key, None)
    for key in ("unread", "flagged", "has_attachments"):
        normalize_bool_field(formatted, key)
    return formatted


def normalize_mail_body_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    return format_row(row)


def normalize_mail_part_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["attachment_remote_spec"] = parse_optional_json_object_field(
        formatted.get("attachment_remote_spec_json"),
    )
    formatted.pop("attachment_remote_spec_json", None)
    normalize_bool_field(formatted, "is_inline")
    return formatted
