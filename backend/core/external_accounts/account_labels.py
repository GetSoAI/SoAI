"""SoAI - External account display label resolution [backend/core/external_accounts/account_labels.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_external_account_display_label",)


def resolve_external_account_display_label(
    account: JSONDict,
    external_account: JSONDict,
    *,
    unavailable_message: str,
) -> str:
    label = coerce_optional_trimmed_str(external_account.get("label"))
    if label is not None:
        return label
    account_id = coerce_optional_trimmed_str(account.get("id"))
    if account_id is not None:
        return account_id
    raise StateError(unavailable_message)
