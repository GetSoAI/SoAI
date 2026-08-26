"""SoAI - Mail account payload helpers [backend/features/mail/account_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from core.validation.json_object_fields import (
    extract_known_json_object_fields_from_section,
    validate_allowed_json_object_fields,
)

__all__ = ("extract_mail_account_payload",)

_MAIL_ACCOUNT_FIELDS: tuple[str, ...] = (
    "protocol",
    "inbound_host",
    "inbound_port",
    "inbound_security",
    "smtp_host",
    "smtp_security",
    "smtp_port",
    "folder_mapping",
)
_ROOT_FIELDS: tuple[str, ...] = ("label", "username", "auth", "transport")


def extract_mail_account_payload(payload: JSONDict) -> JSONDict:
    validate_allowed_json_object_fields(
        payload,
        allowed_field_names=_ROOT_FIELDS,
        label="mail account payload",
    )
    return extract_known_json_object_fields_from_section(
        payload,
        section_name="transport",
        field_names=_MAIL_ACCOUNT_FIELDS,
    )
