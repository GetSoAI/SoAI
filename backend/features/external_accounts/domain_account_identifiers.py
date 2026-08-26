"""SoAI - Domain account identifier readers [backend/features/external_accounts/domain_account_identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.validation.record_fields import require_non_empty_str

__all__ = (
    "require_domain_account_id",
    "require_domain_external_account_id",
)


def require_domain_account_id(account: JSONDict, *, domain_label: str) -> str:
    return require_non_empty_str(
        account.get("id"),
        label=f"{domain_label} account id",
        build_error=StateError,
        invalid_message=f"{domain_label} account is missing its id.",
    )


def require_domain_external_account_id(account: JSONDict, *, domain_label: str) -> str:
    return require_non_empty_str(
        account.get("external_account_id"),
        label=f"{domain_label} account external account id",
        build_error=StateError,
        invalid_message=f"{domain_label} account is missing its external account id.",
    )
