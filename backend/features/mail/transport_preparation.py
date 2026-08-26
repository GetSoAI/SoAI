"""SoAI - Mail service transport preparation [backend/features/mail/transport_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mail.protocols import MailTransportPreparationProtocol
from features.mail.transport_context import (
    PreparedMailTransportContext,
    prepare_mail_transport_context,
)

__all__ = ("prepare_service_mail_transport_context",)


async def prepare_service_mail_transport_context(
    service: MailTransportPreparationProtocol,
    *,
    user_id: int,
    account_id: str,
) -> PreparedMailTransportContext:
    async with service.account_lock(user_id=user_id, account_id=account_id):
        return await prepare_mail_transport_context(
            config=service.config,
            runtime_flags=service.runtime_flags,
            database_mail=service.database_mail,
            external_accounts=service.external_accounts,
            user_id=user_id,
            account_id=account_id,
        )
