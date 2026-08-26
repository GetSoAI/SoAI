"""SoAI - Shared account sync field mappings (last sync) [backend/database/repositories/users/account_sync_field_mappings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str
from database.repositories.users.account_validation import optional_epoch_ms
from database.repositories.users.domain_account_payload_mapping import (
    AccountPayloadFieldMapping,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from database.core.sqlite_values import SQLiteValue

__all__ = ("build_account_sync_field_mappings",)


def _optional_last_sync_at_ms(value: JSONValue) -> SQLiteValue:
    return optional_epoch_ms(value, label="last_sync_at_ms")


def build_account_sync_field_mappings() -> tuple[AccountPayloadFieldMapping, ...]:
    return (
        AccountPayloadFieldMapping(
            "last_sync_at_ms",
            "last_sync_at_ms",
            _optional_last_sync_at_ms,
        ),
        AccountPayloadFieldMapping(
            "last_sync_error",
            "last_sync_error",
            coerce_optional_trimmed_str,
        ),
    )
