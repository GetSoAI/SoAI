"""SoAI - Never-reused WebUI account ID allocation [backend/database/repositories/users/user_account_id_allocation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX


def sync_allocate_webui_account_id(conn: sqlite3.Connection) -> int:
    sequence_row = conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = 'webui_users'"
    ).fetchone()
    sequence_id = int(sequence_row[0]) if sequence_row is not None else 0
    maximum_row = conn.execute("SELECT max(id) FROM webui_users").fetchone()
    maximum_id = int(maximum_row[0]) if maximum_row and maximum_row[0] is not None else 0
    user_id = max(sequence_id, maximum_id) + 1
    if user_id > JAVASCRIPT_SAFE_INTEGER_MAX:
        raise StateError("WebUI account ID space is exhausted.")
    return user_id


__all__ = ("sync_allocate_webui_account_id",)
