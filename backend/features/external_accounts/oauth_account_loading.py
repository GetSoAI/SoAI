"""SoAI - Locked external OAuth account loading [backend/features/external_accounts/oauth_account_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.errors.exceptions import ValidationError
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.external_accounts.state import require_oauth2_account
from core.types.json import JSONDict

__all__ = ("locked_oauth2_external_account",)


@asynccontextmanager
async def locked_oauth2_external_account(
    external_accounts: ExternalAccountsServiceProtocol,
    *,
    user_id: int,
    external_account_id: str,
) -> AsyncGenerator[JSONDict]:
    async with external_accounts.account_lock(
        user_id=user_id,
        external_account_id=external_account_id,
    ):
        account = await external_accounts.get_account(
            user_id,
            external_account_id,
            decrypt_secrets=True,
        )
        if account is None:
            raise ValidationError("External account not found.")
        require_oauth2_account(account)
        yield account
