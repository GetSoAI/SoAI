"""SoAI - Linked domain account loading invariants [backend/features/external_accounts/domain_account_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.protocols import LinkedDomainAccountStorageProtocol
from core.types.json import JSONDict

__all__ = ("require_linked_domain_account",)


async def require_linked_domain_account(
    storage: LinkedDomainAccountStorageProtocol,
    *,
    user_id: int,
    account_id: str,
    missing_message: str,
) -> JSONDict:
    account = await storage.get_account(
        user_id=user_id,
        account_id=account_id,
    )
    if account is None:
        raise ValidationError(missing_message)
    return account
