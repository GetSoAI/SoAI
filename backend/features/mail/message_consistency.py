"""SoAI - Mail message consistency guards [backend/features/mail/message_consistency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from features.mail.mail_record_context import require_message_account_id

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol

__all__ = ("reload_message_for_locked_account",)


async def reload_message_for_locked_account(
    database_mail: DatabaseMailProtocol,
    *,
    user_id: int,
    message_id: str,
    account_id: str,
) -> JSONDict:
    current_message = await database_mail.get_message(
        user_id=user_id,
        message_id=message_id,
    )
    if current_message is None:
        raise ValidationError("Mail message not found.")
    if require_message_account_id(current_message) != account_id:
        raise StateError("Mail message account changed unexpectedly.")
    return current_message
