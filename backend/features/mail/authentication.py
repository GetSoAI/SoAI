"""SoAI - Mail transport authentication helpers [backend/features/mail/authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.external_accounts.authentication import (
    resolve_external_account_authentication,
)

if TYPE_CHECKING:
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.types.json import JSONDict
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = ("resolve_mail_authentication",)


async def resolve_mail_authentication(
    *,
    runtime_state: MailAccountRuntimeState,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
) -> JSONDict:
    resolved_authentication = await resolve_external_account_authentication(
        external_accounts=external_accounts,
        external_account=runtime_state.external_account,
        user_id=user_id,
        missing_access_token_message="OAuth access token is not available.",
        build_xoauth2_sasl=True,
    )
    if resolved_authentication.auth_type == "password":
        return {
            "auth_type": resolved_authentication.auth_type,
            "username": resolved_authentication.username,
            "password": resolved_authentication.password,
        }
    return {
        "auth_type": resolved_authentication.auth_type,
        "username": resolved_authentication.username,
        "access_token": resolved_authentication.access_token,
        "xoauth2_sasl": resolved_authentication.xoauth2_sasl,
    }
