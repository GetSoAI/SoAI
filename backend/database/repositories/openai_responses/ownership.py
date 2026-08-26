"""SoAI - OpenAI Responses persisted ownership [backend/database/repositories/openai_responses/ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    normalize_optional_user_id,
    optional_storage_text,
    read_stored_optional_api_key_id,
    read_stored_optional_user_id,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "ResponseOwner",
    "normalize_response_owner",
    "read_stored_response_owner",
)

_ANONYMOUS_OWNER_PREFIX = "__anon__:"


@dataclass(frozen=True, slots=True)
class ResponseOwner:
    user_id: int | None
    api_key_id: str | None
    anonymous_owner_id: str | None


def normalize_response_owner(
    *,
    user_id: int | None,
    api_key_id: str | None,
) -> ResponseOwner:
    normalized_user_id = normalize_optional_user_id(user_id)
    normalized_owner_key = normalize_optional_api_key_id(api_key_id)
    if normalized_owner_key is not None and normalized_owner_key.startswith(
        _ANONYMOUS_OWNER_PREFIX
    ):
        if len(normalized_owner_key) == len(_ANONYMOUS_OWNER_PREFIX):
            raise ValidationError("Anonymous response ownership is invalid.")
        if normalized_user_id is not None:
            raise ValidationError("Anonymous response ownership cannot include a user.")
        normalized_api_key_id = None
        anonymous_owner_id = normalized_owner_key
    else:
        normalized_api_key_id = normalized_owner_key
        anonymous_owner_id = None
    if normalized_user_id is None and normalized_api_key_id is None and anonymous_owner_id is None:
        raise ValidationError("Response ownership is required.")
    return ResponseOwner(
        user_id=normalized_user_id,
        api_key_id=normalized_api_key_id,
        anonymous_owner_id=anonymous_owner_id,
    )


def read_stored_response_owner(row: SQLiteRowDict) -> ResponseOwner:
    required_fields = ("user_id", "api_key_id", "anonymous_owner_id")
    if any(field not in row for field in required_fields):
        raise ValidationError("Stored response ownership is invalid.")
    user_id = read_stored_optional_user_id(
        row["user_id"],
        error_message="Stored response ownership is invalid.",
    )
    api_key_id = read_stored_optional_api_key_id(
        row["api_key_id"],
        error_message="Stored response ownership is invalid.",
    )
    anonymous_owner_id = optional_storage_text(
        row["anonymous_owner_id"],
        field="anonymous_owner_id",
    )
    if anonymous_owner_id is not None:
        if not anonymous_owner_id.startswith(_ANONYMOUS_OWNER_PREFIX) or len(
            anonymous_owner_id
        ) == len(_ANONYMOUS_OWNER_PREFIX):
            raise ValidationError("Stored response ownership is invalid.")
        if user_id is not None or api_key_id is not None:
            raise ValidationError("Stored response ownership is invalid.")
    owner_count = sum(value is not None for value in (user_id, api_key_id, anonymous_owner_id))
    if owner_count < 1:
        raise ValidationError("Stored response ownership is invalid.")
    return ResponseOwner(
        user_id=user_id,
        api_key_id=api_key_id,
        anonymous_owner_id=anonymous_owner_id,
    )
