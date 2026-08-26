"""SoAI - Mail account record validation [backend/features/mail/mail_account_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("require_mail_account_protocol",)


def require_mail_account_protocol(account: JSONDict) -> str:
    protocol = coerce_optional_trimmed_str(account.get("protocol"))
    normalized_protocol = protocol.lower() if protocol is not None else ""
    if normalized_protocol not in {"imap", "pop3"}:
        raise StateError("Mail account protocol is invalid.")
    return normalized_protocol
