"""SoAI - Username-scoped authentication bucket cleanup [backend/database/repositories/users/username_auth_bucket_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.auth.auth_failure_buckets import (
    WEBUI_LOGIN_IP_NAME_PREFIX,
    WEBUI_LOGIN_USER_PREFIX,
)
from core.users.username import require_canonical_username


def sync_clear_username_auth_buckets(conn: sqlite3.Connection, username: str) -> None:
    canonical_username = require_canonical_username(username)
    conn.execute(
        "DELETE FROM auth_failure_buckets WHERE bucket_id = ?",
        (f"{WEBUI_LOGIN_USER_PREFIX}{canonical_username}",),
    )
    conn.execute(
        """
        DELETE FROM auth_failure_buckets
        WHERE substr(bucket_id, 1, ?) = ?
          AND substr(bucket_id, length(bucket_id) - ? + 1) = ?
          AND substr(bucket_id, length(bucket_id) - ?, 1) = ':'
        """,
        (
            len(WEBUI_LOGIN_IP_NAME_PREFIX),
            WEBUI_LOGIN_IP_NAME_PREFIX,
            len(canonical_username),
            canonical_username,
            len(canonical_username),
        ),
    )


__all__ = ("sync_clear_username_auth_buckets",)
