"""SoAI - Owner private skills and captured execution schema [backend/database/schema_scripts/skills.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.skills.limits import MAX_DESCRIPTION_CHARACTERS, MAX_NAME_CHARACTERS, MAX_PACKAGE_BYTES
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script

__all__ = (
    "apply_skills_schema",
    "build_skills_schema_sql",
)


def apply_skills_schema(connection: sqlite3.Connection) -> None:
    execute_sql_script(connection, build_skills_schema_sql())


def build_skills_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_skill_libraries (
            user_id INTEGER PRIMARY KEY REFERENCES webui_users(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL CHECK(revision BETWEEN 0 AND {JAVASCRIPT_SAFE_INTEGER_MAX})
        ) STRICT;
        CREATE TABLE IF NOT EXISTS webui_skills (
            user_id INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            skill_id TEXT NOT NULL,
            upload_id TEXT NOT NULL,
            upload_digest TEXT NOT NULL CHECK(length(upload_digest) = 64),
            package_digest TEXT NOT NULL CHECK(length(package_digest) = 64),
            name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND {MAX_NAME_CHARACTERS}),
            description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND {MAX_DESCRIPTION_CHARACTERS}),
            manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json) AND json_type(manifest_json) = 'object'),
            profile_json TEXT NOT NULL CHECK(json_valid(profile_json) AND json_type(profile_json) = 'object'),
            profile_digest TEXT NOT NULL CHECK(length(profile_digest) = 64),
            disable_model_invocation INTEGER NOT NULL CHECK(disable_model_invocation IN (0, 1)),
            user_invocable INTEGER NOT NULL CHECK(user_invocable IN (0, 1)),
            size_bytes INTEGER NOT NULL CHECK(size_bytes BETWEEN 0 AND {MAX_PACKAGE_BYTES}),
            created_at_ms INTEGER NOT NULL,
            removed_at_ms INTEGER CHECK(removed_at_ms IS NULL OR removed_at_ms >= created_at_ms),
            PRIMARY KEY(user_id, skill_id),
            UNIQUE(user_id, upload_id)
        ) WITHOUT ROWID, STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_installed_name
            ON webui_skills(user_id, name) WHERE removed_at_ms IS NULL;
        CREATE TABLE IF NOT EXISTS webui_skill_import_batches (
            user_id INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            upload_id TEXT NOT NULL,
            upload_digest TEXT NOT NULL CHECK(length(upload_digest) = 64),
            created_at_ms INTEGER NOT NULL,
            PRIMARY KEY(user_id, upload_id)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_skill_import_batch_members (
            user_id INTEGER NOT NULL,
            upload_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            source_root TEXT NOT NULL,
            PRIMARY KEY(user_id, upload_id, source_root),
            UNIQUE(user_id, skill_id),
            FOREIGN KEY(user_id, upload_id) REFERENCES webui_skill_import_batches(user_id, upload_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_skill_supporting_members (
            user_id INTEGER NOT NULL,
            upload_id TEXT NOT NULL,
            path TEXT NOT NULL,
            content BLOB NOT NULL,
            digest TEXT NOT NULL CHECK(length(digest) = 64),
            PRIMARY KEY(user_id, upload_id, path),
            FOREIGN KEY(user_id, upload_id) REFERENCES webui_skill_import_batches(user_id, upload_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_skill_support_bindings (
            user_id INTEGER NOT NULL,
            skill_id TEXT NOT NULL,
            upload_id TEXT NOT NULL,
            path TEXT NOT NULL,
            PRIMARY KEY(user_id, skill_id, path),
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id, upload_id, path) REFERENCES webui_skill_supporting_members(user_id, upload_id, path)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_skill_members (
            user_id INTEGER NOT NULL,
            skill_id TEXT NOT NULL,
            path TEXT NOT NULL,
            is_directory INTEGER NOT NULL CHECK(is_directory IN (0, 1)),
            content BLOB NOT NULL,
            digest TEXT NOT NULL CHECK(length(digest) = 64),
            CHECK(is_directory = 0 OR length(content) = 0),
            PRIMARY KEY(user_id, skill_id, path),
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_skill_owner
            ON webui_conversations(user_id, id);
        CREATE TABLE IF NOT EXISTS webui_conversation_skill_state (
            user_id INTEGER NOT NULL,
            conv_id TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK(revision BETWEEN 0 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            PRIMARY KEY(user_id, conv_id),
            FOREIGN KEY(user_id, conv_id) REFERENCES webui_conversations(user_id, id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_conversation_skills (
            user_id INTEGER NOT NULL,
            conv_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            PRIMARY KEY(user_id, conv_id, skill_id),
            FOREIGN KEY(user_id, conv_id) REFERENCES webui_conversation_skill_state(user_id, conv_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id)
        ) WITHOUT ROWID, STRICT;
        CREATE INDEX IF NOT EXISTS idx_conversation_skills_library
            ON webui_conversation_skills(user_id, skill_id, conv_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_inputs_skill_owner
            ON webui_conversation_inputs(user_id, conv_id, input_id);
        CREATE TABLE IF NOT EXISTS webui_skill_snapshots (
            user_id INTEGER NOT NULL,
            conv_id TEXT NOT NULL,
            input_id TEXT NOT NULL,
            root_input_id TEXT NOT NULL,
            selection_revision INTEGER NOT NULL CHECK(selection_revision BETWEEN 0 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            PRIMARY KEY(user_id, conv_id, input_id),
            FOREIGN KEY(user_id, conv_id, input_id) REFERENCES webui_conversation_inputs(user_id, conv_id, input_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_skill_snapshot_members (
            user_id INTEGER NOT NULL,
            conv_id TEXT NOT NULL,
            input_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            package_digest TEXT NOT NULL CHECK(length(package_digest) = 64),
            explicit_ordinal INTEGER CHECK(explicit_ordinal IS NULL OR explicit_ordinal >= 0),
            profile_digest TEXT NOT NULL CHECK(length(profile_digest) = 64),
            invocation_arguments TEXT,
            PRIMARY KEY(user_id, conv_id, input_id, skill_id),
            FOREIGN KEY(user_id, conv_id, input_id) REFERENCES webui_skill_snapshots(user_id, conv_id, input_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id)
        ) WITHOUT ROWID, STRICT;
        CREATE INDEX IF NOT EXISTS idx_skill_snapshot_retention
            ON webui_skill_snapshot_members(user_id, skill_id, conv_id, input_id);
        CREATE TABLE IF NOT EXISTS webui_skill_turn_checkpoints (
            user_id INTEGER NOT NULL,
            conv_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            input_id TEXT NOT NULL,
            activation_json TEXT NOT NULL CHECK(json_valid(activation_json) AND json_type(activation_json) = 'object'),
            PRIMARY KEY(conv_id, user_id, turn_id),
            FOREIGN KEY(conv_id, user_id, turn_id) REFERENCES webui_agent_turns(conv_id, user_id, turn_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id, conv_id, input_id) REFERENCES webui_skill_snapshots(user_id, conv_id, input_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE INDEX IF NOT EXISTS idx_skill_turn_input
            ON webui_skill_turn_checkpoints(user_id, conv_id, input_id);
        CREATE TABLE IF NOT EXISTS webui_skill_materializations (
            request_id TEXT PRIMARY KEY,
            operation_key TEXT NOT NULL UNIQUE CHECK(length(operation_key) = 64),
            user_id INTEGER NOT NULL,
            skill_id TEXT NOT NULL,
            request_json TEXT NOT NULL CHECK(json_valid(request_json) AND json_type(request_json) = 'object'),
            resources_json TEXT NOT NULL CHECK(json_valid(resources_json) AND json_type(resources_json) = 'array'),
            staging_identity_json TEXT CHECK(staging_identity_json IS NULL OR json_valid(staging_identity_json)),
            publication_identity_json TEXT CHECK(publication_identity_json IS NULL OR json_valid(publication_identity_json)),
            terminal_status TEXT CHECK(terminal_status IS NULL OR terminal_status IN ('completed', 'failed', 'cancelled')),
            terminal_result TEXT CHECK(terminal_result IS NULL OR json_valid(terminal_result)),
            FOREIGN KEY(user_id, skill_id) REFERENCES webui_skills(user_id, skill_id) ON DELETE CASCADE,
            CHECK(terminal_status != 'completed' OR publication_identity_json IS NOT NULL)
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_skill_materialization_retention
            ON webui_skill_materializations(user_id, skill_id) WHERE terminal_status IS NULL;
    """
