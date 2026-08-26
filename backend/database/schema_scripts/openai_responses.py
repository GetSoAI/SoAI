"""SoAI - Database schema: OpenAI Responses storage tables [backend/database/schema_scripts/openai_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.validation.epoch import EPOCH_MS_MIN
from database.core.schema_sql import normalize_schema_sql, read_schema_object_sql
from database.sql.script import execute_sql_script

__all__ = ("apply_openai_responses_schema",)

_RESPONSE_TABLE = "openai_responses"
_INPUT_ITEMS_TABLE = "openai_response_input_items"
_EVENTS_TABLE = "openai_response_events"


def _response_table_sql(table_name: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            response_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id INTEGER REFERENCES webui_users(id) ON DELETE CASCADE,
            api_key_id TEXT REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            anonymous_owner_id TEXT,
            model TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            status TEXT NOT NULL,
            store INTEGER NOT NULL CHECK(store IN (0, 1)),
            is_background INTEGER NOT NULL DEFAULT 0 CHECK(is_background IN (0, 1)),
            stream_enabled INTEGER NOT NULL DEFAULT 0 CHECK(stream_enabled IN (0, 1)),
            response_json TEXT NOT NULL CHECK(json_valid(response_json)),
            CHECK(user_id IS NOT NULL OR api_key_id IS NOT NULL OR anonymous_owner_id IS NOT NULL),
            CHECK(
                anonymous_owner_id IS NULL OR (
                    anonymous_owner_id GLOB '__anon__:*'
                    AND length(anonymous_owner_id) > length('__anon__:')
                    AND user_id IS NULL
                    AND api_key_id IS NULL
                )
            )
        ) STRICT
    """


def _input_items_table_sql(table_name: str, response_table: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            response_id TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            item_json TEXT NOT NULL CHECK(json_valid(item_json)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY (response_id, item_index),
            UNIQUE (response_id, item_id),
            FOREIGN KEY (response_id) REFERENCES {response_table}(response_id) ON DELETE CASCADE
        ) STRICT
    """


def _events_table_sql(table_name: str, response_table: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            response_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            event_json TEXT NOT NULL CHECK(json_valid(event_json)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY (response_id, sequence),
            FOREIGN KEY (response_id) REFERENCES {response_table}(response_id) ON DELETE CASCADE
        ) STRICT
    """


def _target_table_sql() -> dict[str, str]:
    return {
        _RESPONSE_TABLE: _response_table_sql(_RESPONSE_TABLE),
        _INPUT_ITEMS_TABLE: _input_items_table_sql(_INPUT_ITEMS_TABLE, _RESPONSE_TABLE),
        _EVENTS_TABLE: _events_table_sql(_EVENTS_TABLE, _RESPONSE_TABLE),
    }


def _target_stored_table_sql() -> dict[str, str]:
    expected = sqlite3.connect(":memory:")
    try:
        _create_tables(expected)
        return {
            table_name: str(read_schema_object_sql(expected, object_type="table", name=table_name))
            for table_name in _target_table_sql()
        }
    finally:
        expected.close()


def _existing_table_sql(conn: sqlite3.Connection) -> dict[str, str | None]:
    return {
        table_name: read_schema_object_sql(conn, object_type="table", name=table_name)
        for table_name in _target_table_sql()
    }


def _create_tables(conn: sqlite3.Connection) -> None:
    for statement in _target_table_sql().values():
        conn.execute(statement)


def _validate_existing_tables(existing_sql: dict[str, str | None]) -> None:
    for table_name, expected_sql in _target_stored_table_sql().items():
        actual_sql = existing_sql[table_name]
        if actual_sql is None:
            raise StateError("OpenAI Responses schema is incomplete.")
        if normalize_schema_sql(actual_sql) != normalize_schema_sql(expected_sql):
            raise StateError("OpenAI Responses schema does not match the canonical V1 shape.")


def _apply_indexes(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        """
        CREATE INDEX IF NOT EXISTS idx_openai_responses_task_id ON openai_responses(task_id);
        CREATE INDEX IF NOT EXISTS idx_openai_responses_owner
            ON openai_responses(user_id, api_key_id, anonymous_owner_id);
        CREATE INDEX IF NOT EXISTS idx_openai_responses_created_at ON openai_responses(created_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_openai_responses_background_stream
            ON openai_responses(is_background, stream_enabled, created_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_openai_response_input_items_id
            ON openai_response_input_items(response_id, item_id);
        CREATE INDEX IF NOT EXISTS idx_openai_response_events_response_id
            ON openai_response_events(response_id, sequence);
        """,
    )


def apply_openai_responses_schema(conn: sqlite3.Connection) -> None:
    existing_sql = _existing_table_sql(conn)
    existing_count = sum(value is not None for value in existing_sql.values())
    if existing_count == 0:
        _create_tables(conn)
        existing_sql = _existing_table_sql(conn)
    elif existing_count != len(existing_sql):
        raise StateError("OpenAI Responses schema is incomplete.")
    _validate_existing_tables(existing_sql)
    _apply_indexes(conn)
