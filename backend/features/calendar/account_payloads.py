"""SoAI - Calendar account payload helpers [backend/features/calendar/account_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from core.validation.json_object_fields import (
    extract_known_json_object_fields_from_section,
    validate_allowed_json_object_fields,
)

__all__ = ("extract_calendar_account_payload",)

_CALENDAR_ACCOUNT_FIELDS: tuple[str, ...] = (
    "caldav_base_url",
    "linked_mail_account_id",
    "discovered_principal",
)
_ROOT_FIELDS: tuple[str, ...] = ("label", "username", "auth", "transport")


def extract_calendar_account_payload(payload: JSONDict) -> JSONDict:
    validate_allowed_json_object_fields(
        payload,
        allowed_field_names=_ROOT_FIELDS,
        label="calendar account payload",
    )
    return extract_known_json_object_fields_from_section(
        payload,
        section_name="transport",
        field_names=_CALENDAR_ACCOUNT_FIELDS,
    )
