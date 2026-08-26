"""SoAI - Mail IMAP command primitives [backend/features/mail/imap_command_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("quote_imap_mailbox", "require_imap_ok")


def quote_imap_mailbox(value: str) -> str:
    return f'"{value}"'


def require_imap_ok(status: str, message: str) -> None:
    if status != "OK":
        raise ValidationError(message)
