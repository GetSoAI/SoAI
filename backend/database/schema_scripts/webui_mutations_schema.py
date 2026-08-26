"""SoAI - Durable WebUI identity mutation schema [backend/database/schema_scripts/webui_mutations_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.identity_mutation_contract import (
    IDENTITY_MUTATION_FAILURE_CODES,
    IDENTITY_MUTATION_STATUSES,
    IDENTITY_MUTATION_TYPES,
    sql_values,
)
from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script


def build_webui_mutations_schema_sql() -> str:
    operation_types = sql_values(IDENTITY_MUTATION_TYPES)
    statuses = sql_values(IDENTITY_MUTATION_STATUSES)
    failure_codes = sql_values(IDENTITY_MUTATION_FAILURE_CODES)
    return f"""
        CREATE TABLE IF NOT EXISTS webui_user_mutations (
            actor_user_id INTEGER NOT NULL
                CHECK(actor_user_id BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            operation_id TEXT NOT NULL
                CHECK(length(operation_id) = 36)
                CHECK(operation_id = lower(operation_id))
                CHECK(substr(operation_id, 15, 1) = '7')
                CHECK(substr(operation_id, 20, 1) IN ('8', '9', 'a', 'b')),
            operation_type TEXT NOT NULL CHECK(operation_type IN ({operation_types})),
            target_user_id INTEGER NOT NULL
                CHECK(target_user_id BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            requested_username TEXT,
            completed_at_ms INTEGER NOT NULL
                CHECK(completed_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            retain_until_ms INTEGER NOT NULL
                CHECK(retain_until_ms BETWEEN completed_at_ms AND {EPOCH_MS_MAX}),
            status TEXT NOT NULL CHECK(status IN ({statuses})),
            error_code TEXT CHECK(error_code IS NULL OR error_code IN ({failure_codes})),
            trace_id TEXT,
            previous_username TEXT,
            new_username TEXT,
            new_identity_revision INTEGER
                CHECK(new_identity_revision IS NULL OR new_identity_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            previous_password_revision INTEGER
                CHECK(previous_password_revision IS NULL OR previous_password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            new_password_revision INTEGER
                CHECK(new_password_revision IS NULL OR new_password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            PRIMARY KEY(actor_user_id, operation_id),
            CHECK(
                (operation_type = 'username_rename'
                    AND requested_username IS NOT NULL
                    AND length(requested_username) BETWEEN 3 AND 50
                    AND requested_username = lower(requested_username)
                    AND requested_username NOT GLOB '*[^a-z0-9_.-]*')
                OR (operation_type = 'password_change' AND requested_username IS NULL)
            ),
            CHECK(
                (status = 'failed'
                    AND error_code IS NOT NULL
                    AND (error_code = 'identity_mutation_failed') = (trace_id IS NOT NULL)
                    AND previous_username IS NULL AND new_username IS NULL
                    AND new_identity_revision IS NULL
                    AND previous_password_revision IS NULL
                    AND new_password_revision IS NULL)
                OR (status = 'committed'
                    AND error_code IS NULL AND trace_id IS NULL
                    AND (
                        (operation_type = 'username_rename'
                            AND previous_username IS NOT NULL
                            AND new_username = requested_username
                            AND new_identity_revision IS NOT NULL
                            AND previous_password_revision IS NULL
                            AND new_password_revision IS NULL)
                        OR (operation_type = 'password_change'
                            AND previous_username IS NULL
                            AND new_username IS NULL
                            AND new_identity_revision IS NULL
                            AND previous_password_revision IS NOT NULL
                            AND new_password_revision = previous_password_revision + 1)
                    ))
            )
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_user_mutations_retention
            ON webui_user_mutations(retain_until_ms);
        CREATE INDEX IF NOT EXISTS idx_webui_user_mutations_target
            ON webui_user_mutations(target_user_id, completed_at_ms);
    """


def apply_webui_mutations_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_webui_mutations_schema_sql())


__all__ = ("apply_webui_mutations_schema", "build_webui_mutations_schema_sql")
