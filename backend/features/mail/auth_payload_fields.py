"""SoAI - Mail authentication payload field extraction [backend/features/mail/auth_payload_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = (
    "extract_mail_auth_payload_fields",
    "require_mail_auth_payload_username",
)


def extract_mail_auth_payload_fields(auth_payload: JSONDict) -> tuple[str, str, str, str]:
    auth_type_value = auth_payload.get("auth_type")
    auth_type = auth_type_value.strip() if isinstance(auth_type_value, str) else ""
    username_value = auth_payload.get("username")
    username = username_value.strip() if isinstance(username_value, str) else ""
    password_value = auth_payload.get("password")
    password = password_value if isinstance(password_value, str) else ""
    sasl_value = auth_payload.get("xoauth2_sasl")
    sasl = sasl_value.strip() if isinstance(sasl_value, str) else ""
    return (auth_type, username, password, sasl)


def require_mail_auth_payload_username(auth_payload: JSONDict) -> str:
    _auth_type, username, _password, _sasl = extract_mail_auth_payload_fields(auth_payload)
    if not username:
        raise ValidationError("External account username is required.")
    return username
