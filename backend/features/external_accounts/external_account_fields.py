"""SoAI - External account field readers [backend/features/external_accounts/external_account_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.errors.exceptions import ValidationError
from core.external_accounts.state import require_auth_type
from core.types.json import JSONDict
from core.validation.record_fields import require_non_empty_str

__all__ = (
    "require_external_account_auth_type",
    "require_external_account_id",
    "require_external_account_username",
)


def require_external_account_id(
    external_account: JSONDict,
    *,
    build_error: Callable[[str], Exception],
) -> str:
    return require_non_empty_str(
        external_account.get("id"),
        label="external account id",
        build_error=build_error,
        invalid_message="External account id is required.",
    )


def require_external_account_username(
    external_account: JSONDict,
    *,
    build_error: Callable[[str], Exception],
) -> str:
    return require_non_empty_str(
        external_account.get("username"),
        label="external account username",
        build_error=build_error,
        invalid_message="External account username is required.",
    )


def require_external_account_auth_type(
    external_account: JSONDict,
    *,
    build_error: Callable[[str], Exception],
) -> str:
    try:
        return require_auth_type(external_account.get("auth_type"))
    except ValidationError as exception:
        raise build_error("External account auth_type is invalid.") from exception
