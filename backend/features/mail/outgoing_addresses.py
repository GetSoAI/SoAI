"""SoAI - Mail outgoing address handling [backend/features/mail/outgoing_addresses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "apply_outgoing_recipients",
    "resolve_account_address",
    "resolve_message_id_domain",
)


def apply_outgoing_recipients(
    *,
    message: EmailMessage,
    mode: str,
    payload: JSONDict,
    base_message: JSONDict | None,
    own_email: str,
) -> None:
    to_addresses = _resolve_recipient_list(
        mode=mode,
        payload_value=payload.get("to"),
        base_message=base_message,
        field_name="to",
        own_email=own_email,
    )
    if not to_addresses:
        raise ValidationError("At least one recipient is required.")
    message["To"] = ", ".join(_format_address(item) for item in to_addresses)
    cc_addresses = _resolve_cc_list(
        mode=mode,
        payload_value=payload.get("cc"),
        base_message=base_message,
        own_email=own_email,
    )
    if cc_addresses:
        message["Cc"] = ", ".join(_format_address(item) for item in cc_addresses)
    bcc_addresses = _parse_address_list(payload.get("bcc"), label="bcc")
    if bcc_addresses:
        message["Bcc"] = ", ".join(_format_address(item) for item in bcc_addresses)


def resolve_account_address(username: str) -> JSONDict:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValidationError("External account username is required.")
    return {"email": normalized_username, "name": None}


def resolve_message_id_domain(email_address: str) -> str:
    parts = email_address.split("@", 1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    return "localhost"


def _resolve_recipient_list(
    *,
    mode: str,
    payload_value: JSONValue,
    base_message: JSONDict | None,
    field_name: str,
    own_email: str,
) -> list[JSONDict]:
    explicit = _parse_address_list(payload_value, label=field_name)
    if explicit:
        return explicit
    if base_message is None:
        return []
    if mode == "reply_all":
        base_from = _coerce_address_entries(base_message.get("from"))
        base_to = _coerce_address_entries(base_message.get("to"))
        return _merge_addresses(base_from + base_to, own_email=own_email)
    if mode == "reply":
        return _merge_addresses(
            _coerce_address_entries(base_message.get("from")),
            own_email=own_email,
        )
    return []


def _resolve_cc_list(
    *,
    mode: str,
    payload_value: JSONValue,
    base_message: JSONDict | None,
    own_email: str,
) -> list[JSONDict]:
    explicit = _parse_address_list(payload_value, label="cc")
    if explicit or mode != "reply_all" or base_message is None:
        return explicit
    return _merge_addresses(
        _coerce_address_entries(base_message.get("cc")),
        own_email=own_email,
    )


def _parse_address_list(value: JSONValue, *, label: str) -> list[JSONDict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be a list.")
    addresses: list[JSONDict] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError(f"{label} entries must be objects.")
        email_value = item.get("email")
        email = email_value.strip() if isinstance(email_value, str) else ""
        if not email:
            raise ValidationError(f"{label} entries require email.")
        name_value = item.get("name")
        name = coerce_optional_trimmed_str(name_value)
        addresses.append({"email": email, "name": name})
    return addresses


def _merge_addresses(addresses: list[JSONDict], *, own_email: str) -> list[JSONDict]:
    merged: list[JSONDict] = []
    seen_emails: set[str] = set()
    own_email_token = own_email.strip().lower()
    for item in addresses:
        email_value = item.get("email")
        email = email_value.strip() if isinstance(email_value, str) else ""
        if not email:
            continue
        lowered = email.lower()
        if lowered == own_email_token or lowered in seen_emails:
            continue
        seen_emails.add(lowered)
        merged.append({"email": email, "name": item.get("name")})
    return merged


def _coerce_address_entries(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    entries: list[JSONDict] = []
    for item in value:
        if isinstance(item, dict):
            entries.append(item)
    return entries


def _format_address(value: JSONDict) -> str:
    name_value = value.get("name")
    name = name_value.strip() if isinstance(name_value, str) else ""
    email_value = value.get("email")
    email = email_value.strip() if isinstance(email_value, str) else ""
    return formataddr((name, email))
