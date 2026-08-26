"""SoAI - Shared external-account authentication resolution [backend/features/external_accounts/authentication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_trimmed_str_or_empty
from features.external_accounts.external_account_fields import (
    require_external_account_auth_type,
    require_external_account_id,
    require_external_account_username,
)

if TYPE_CHECKING:
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.types.json import JSONDict

__all__ = (
    "ExternalAccountAuthentication",
    "resolve_external_account_authentication",
)


@dataclass(frozen=True, slots=True)
class ExternalAccountAuthentication:
    external_account_id: str
    auth_type: str
    username: str
    password: str | None
    access_token: str | None
    xoauth2_sasl: str | None


async def resolve_external_account_authentication(
    *,
    external_accounts: ExternalAccountsServiceProtocol,
    external_account: JSONDict,
    user_id: int,
    missing_access_token_message: str,
    build_xoauth2_sasl: bool,
) -> ExternalAccountAuthentication:
    external_account_id = require_external_account_id(
        external_account,
        build_error=ValidationError,
    )
    async with external_accounts.account_lock(
        user_id=user_id,
        external_account_id=external_account_id,
    ):
        current_external_account = await external_accounts.get_account(
            user_id=user_id,
            external_account_id=external_account_id,
            decrypt_secrets=True,
        )
        if current_external_account is None:
            raise ValidationError("External account not found.")
        username = require_external_account_username(
            current_external_account,
            build_error=ValidationError,
        )
        auth_type = require_external_account_auth_type(
            current_external_account,
            build_error=ValidationError,
        )
        if auth_type == "password":
            password_value = current_external_account.get("password")
            password = (
                password_value if isinstance(password_value, str) and password_value else None
            )
            if password is None:
                raise ValidationError("External account password is required.")
            return ExternalAccountAuthentication(
                external_account_id=external_account_id,
                auth_type=auth_type,
                username=username,
                password=password,
                access_token=None,
                xoauth2_sasl=None,
            )
        access_token_payload = await external_accounts.get_access_token(
            user_id=user_id,
            external_account_id=external_account_id,
        )
        access_token = coerce_trimmed_str_or_empty(access_token_payload.get("access_token"))
        if not access_token:
            raise ValidationError(missing_access_token_message)
        xoauth2_sasl = None
        if build_xoauth2_sasl:
            xoauth2_sasl = external_accounts.build_xoauth2_sasl(
                user_email=username,
                access_token=access_token,
            )
        return ExternalAccountAuthentication(
            external_account_id=external_account_id,
            auth_type=auth_type,
            username=username,
            password=None,
            access_token=access_token,
            xoauth2_sasl=xoauth2_sasl,
        )
