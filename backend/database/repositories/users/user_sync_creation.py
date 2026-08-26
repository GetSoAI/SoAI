"""SoAI - User creation sync database operations [backend/database/repositories/users/user_sync_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.prompts.colors import DEFAULT_PROMPT_COLOR
from core.timing.epoch import epoch_ms
from core.users.account_types import HUMAN_ACCOUNT_TYPE
from core.users.username import require_canonical_username
from core.workspaces.user_workspace_path import default_user_workspace_path
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.user_account_id_allocation import (
    sync_allocate_webui_account_id,
)
from database.repositories.users.user_event_outbox import sync_enqueue_user_domain_event
from database.repositories.users.user_sync_queries import sync_get_human_user_by_id
from database.repositories.users.username_auth_bucket_cleanup import (
    sync_clear_username_auth_buckets,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_create_example_prompt",
    "sync_create_user",
)


def sync_create_user(
    conn: sqlite3.Connection,
    username: str,
    hashed_password: str,
    is_admin: bool,
) -> JSONDict:
    try:
        now = epoch_ms()
        normalized_username = require_canonical_username(username)
        user_id = sync_allocate_webui_account_id(conn)
        default_workspace = default_user_workspace_path(user_id)
        cursor = conn.execute(
            """
            INSERT INTO webui_users (
                id, username, account_type, hashed_password, is_admin, created_at_ms,
                password_changed_at_ms, password_revision, workspace_path,
                default_workspace_path, identity_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                normalized_username,
                HUMAN_ACCOUNT_TYPE,
                hashed_password,
                int(is_admin),
                now,
                now,
                1,
                default_workspace,
                default_workspace,
                1,
            ),
        )
        if cursor.lastrowid != user_id:
            raise StateError("INSERT did not preserve the allocated WebUI account ID.")
        sync_clear_username_auth_buckets(conn, normalized_username)
        result = sync_get_human_user_by_id(conn, user_id)
        if result is None:
            raise StateError("User not found after INSERT")
        sync_enqueue_user_domain_event(
            conn,
            event_type="UserCreatedEvent",
            created_at_ms=now,
            user_id=user_id,
            username=str(result.get("username") or ""),
            is_admin=bool(int(is_admin)),
            identity_revision=1,
        )
        return result
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type == "unique" and detail == "webui_users.username":
            raise ConflictError(f"Username '{username}' already exists.") from exception
        raise StateError(
            f"WebUI user creation violated {detail or constraint_type}."
        ) from exception


def sync_create_example_prompt(conn: sqlite3.Connection, user_id: int) -> None:
    prompt_id = uuid.uuid4().hex
    now = epoch_ms()
    conn.execute(
        """
        INSERT INTO webui_prompts (
            id, user_id, name, content, color, created_at_ms, modified_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prompt_id,
            user_id,
            "Example",
            (
                "You can create and organize your prompt templates here. Edit or "
                "delete this example to get started!"
            ),
            DEFAULT_PROMPT_COLOR,
            now,
            now,
        ),
    )
