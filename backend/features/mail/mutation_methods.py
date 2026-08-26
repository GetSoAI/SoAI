"""SoAI - Mail service mutation methods [backend/features/mail/mutation_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.external_accounts.domain_account_actions import (
    coerce_action_status,
    format_account_action_result,
)
from features.mail.internal_protocols import MailRuntimeServiceProtocol
from features.mail.mail_cache_sync import sync_mail_account_cache
from features.mail.mail_compose import compose_message_method
from features.mail.mail_folder_mutations import mutate_folder_method
from features.mail.mail_message_mutations import mutate_message_method

__all__ = (
    "compose_message_method",
    "sync_account_method",
    "update_folder_method",
    "update_message_method",
)


async def sync_account_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    folder_id: str | None,
) -> JSONDict:
    async with self.account_lock(user_id=user_id, account_id=account_id):
        account = await self.database_mail.get_account(user_id=user_id, account_id=account_id)
        if account is None:
            raise ValidationError("Mail account not found.")
        details = await sync_mail_account_cache(
            self,
            user_id=user_id,
            account_id=account_id,
            folder_id=folder_id,
        )
        return format_account_action_result(
            account_id=account_id,
            account_type="mail",
            status=coerce_action_status(details.get("status"), default_value="ready"),
            details=details,
        )


async def update_message_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    message_id: str,
    action: str,
    destination_folder_id: str | None,
) -> JSONDict:
    return await mutate_message_method(
        self,
        user_id=user_id,
        message_id=message_id,
        action=action,
        destination_folder_id=destination_folder_id,
    )


async def update_folder_method(
    self: MailRuntimeServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    action: str,
    folder_id: str | None,
    folder_name: str | None,
) -> JSONDict:
    return await mutate_folder_method(
        self,
        user_id=user_id,
        account_id=account_id,
        action=action,
        folder_id=folder_id,
        folder_name=folder_name,
    )
