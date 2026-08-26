"""SoAI - Shared linked external-account loading flow [backend/features/external_accounts/linked_external_account_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.protocols import LinkedDomainAccountStorageProtocol
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.types.json import JSONDict

__all__ = (
    "LinkedExternalAccountLoadResult",
    "load_linked_external_account",
)


@dataclass(frozen=True, slots=True)
class LinkedExternalAccountLoadResult:
    locked_account: JSONDict
    external_account_id: str
    external_account: JSONDict


async def load_linked_external_account(
    *,
    account_reader: LinkedDomainAccountStorageProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
    decrypt_secrets: bool,
    missing_account_message: str,
    missing_external_account_id_message: str,
    changed_external_account_id_message: str,
    missing_external_account_message: str,
) -> LinkedExternalAccountLoadResult:
    account = await account_reader.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        raise ValidationError(missing_account_message)
    external_account_id = _read_external_account_id(
        account,
        missing_external_account_id_message=missing_external_account_id_message,
    )
    async with external_accounts.account_lock(
        user_id=user_id,
        external_account_id=external_account_id,
    ):
        locked_account = await account_reader.get_account(user_id=user_id, account_id=account_id)
        if locked_account is None:
            raise ValidationError(missing_account_message)
        locked_external_account_id = _read_external_account_id(
            locked_account,
            missing_external_account_id_message=missing_external_account_id_message,
        )
        if locked_external_account_id != external_account_id:
            raise StateError(changed_external_account_id_message)
        external_account = await external_accounts.get_account(
            user_id,
            locked_external_account_id,
            decrypt_secrets=decrypt_secrets,
        )
        if external_account is None:
            remaining_account = await account_reader.get_account(
                user_id=user_id,
                account_id=account_id,
            )
            if remaining_account is None:
                raise ValidationError(missing_account_message)
            remaining_external_account_id = _read_external_account_id(
                remaining_account,
                missing_external_account_id_message=missing_external_account_id_message,
            )
            if remaining_external_account_id != locked_external_account_id:
                raise StateError(changed_external_account_id_message)
            raise StateError(missing_external_account_message)
    return LinkedExternalAccountLoadResult(
        locked_account=locked_account,
        external_account_id=locked_external_account_id,
        external_account=external_account,
    )


def _read_external_account_id(
    account: JSONDict,
    *,
    missing_external_account_id_message: str,
) -> str:
    external_account_id = coerce_optional_trimmed_str(account.get("external_account_id"))
    if external_account_id is None:
        raise StateError(missing_external_account_id_message)
    return external_account_id
