"""SoAI - Database user row normalization to JSON dictionaries [backend/database/repositories/users/user_row_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError, ValidationError
from core.types.json import is_json_value
from core.users.account_types import require_webui_account_type
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.row_formatting import format_row
from database.repositories.users.user_field_coercion import coerce_user_admin_flag

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("normalize_user_row",)


def normalize_user_row(row: SQLiteRowDict | None) -> JSONDict | None:
    normalized = format_row(row)
    if normalized is None:
        return None
    raw_id = row.get("id") if row is not None else None
    if raw_id is not None:
        if isinstance(raw_id, bool):
            raise DatabaseError(
                "User row contains invalid id value.",
                details={"id": raw_id},
                operation="database_users.normalize_user_row",
            )
        coerced_id = coerce_int_from_sqlite(raw_id)
        if coerced_id is None or not 1 <= coerced_id <= JAVASCRIPT_SAFE_INTEGER_MAX:
            raise DatabaseError(
                "User row contains invalid id value.",
                details={"id": raw_id if is_json_value(raw_id) else str(raw_id)},
                operation="database_users.normalize_user_row",
            )
        normalized["id"] = coerced_id
    username = normalized.get("username")
    normalized["username"] = str(username or "")
    account_type = normalized.get("account_type")
    if not isinstance(account_type, str):
        raise DatabaseError(
            "User row is missing account_type.",
            operation="database_users.normalize_user_row",
        )
    try:
        normalized["account_type"] = require_webui_account_type(account_type)
    except ValidationError as exception:
        raise DatabaseError(
            "User row contains invalid account_type.",
            operation="database_users.normalize_user_row",
        ) from exception
    normalized["is_admin"] = coerce_user_admin_flag(normalized.get("is_admin"))
    password_changed_at_ms = row.get("password_changed_at_ms") if row is not None else None
    if password_changed_at_ms is not None:
        coerced_password_changed_at = coerce_int_from_sqlite(password_changed_at_ms)
        if coerced_password_changed_at is None:
            raise DatabaseError(
                "User row contains invalid password_changed_at_ms value.",
                details={"password_changed_at_ms": str(password_changed_at_ms)},
                operation="database_users.normalize_user_row",
            )
        normalized["password_changed_at"] = coerced_password_changed_at
    password_revision = row.get("password_revision") if row is not None else None
    if password_revision is not None:
        coerced_password_revision = coerce_int_from_sqlite(password_revision)
        if (
            coerced_password_revision is None
            or not 1 <= coerced_password_revision <= JAVASCRIPT_SAFE_INTEGER_MAX
        ):
            raise DatabaseError(
                "User row contains invalid password_revision value.",
                details={"password_revision": str(password_revision)},
                operation="database_users.normalize_user_row",
            )
        normalized["password_revision"] = coerced_password_revision
    workspace_value = normalized.get("workspace_path")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        raise DatabaseError(
            "User row contains an invalid workspace_path value.",
            details={"workspace_path": str(workspace_value or "")},
            operation="database_users.normalize_user_row",
        )
    normalized["workspace_path"] = workspace_value
    default_workspace_value = normalized.get("default_workspace_path")
    if not isinstance(default_workspace_value, str) or not default_workspace_value:
        raise DatabaseError(
            "User row contains an invalid default_workspace_path value.",
            operation="database_users.normalize_user_row",
        )
    normalized["default_workspace_path"] = default_workspace_value
    identity_revision_value = normalized.get("identity_revision")
    identity_revision = (
        int(identity_revision_value)
        if isinstance(identity_revision_value, int)
        and not isinstance(identity_revision_value, bool)
        else None
    )
    if identity_revision is None or not 1 <= identity_revision <= JAVASCRIPT_SAFE_INTEGER_MAX:
        raise DatabaseError(
            "User row contains an invalid identity_revision value.",
            operation="database_users.normalize_user_row",
        )
    normalized["identity_revision"] = identity_revision
    normalized.pop("preferences", None)
    return normalized
