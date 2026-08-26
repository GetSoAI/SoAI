"""SoAI - Strict typed WebUI login row mapping [backend/database/repositories/users/user_login_row.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.users.protocols_database import UserLoginRecord
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
)
from database.core.sqlite_values import SQLiteRowDict

__all__ = ("normalize_user_login_row",)

USER_LOGIN_ROW_LABEL = "User login row"


def normalize_user_login_row(row: SQLiteRowDict | None) -> UserLoginRecord | None:
    if row is None:
        return None
    return UserLoginRecord(
        user_id=require_sqlite_row_int(
            row,
            "id",
            label=USER_LOGIN_ROW_LABEL,
            minimum=1,
        ),
        username=require_sqlite_row_non_empty_str(
            row,
            "username",
            label=USER_LOGIN_ROW_LABEL,
        ),
        hashed_password=require_sqlite_row_non_empty_str(
            row,
            "hashed_password",
            label=USER_LOGIN_ROW_LABEL,
        ),
        password_revision=require_sqlite_row_int(
            row,
            "password_revision",
            label=USER_LOGIN_ROW_LABEL,
            minimum=1,
        ),
    )
