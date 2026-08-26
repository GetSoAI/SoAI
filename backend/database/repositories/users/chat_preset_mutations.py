"""SoAI - Transactional chat preset mutation state machines [backend/database/repositories/users/chat_preset_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.chat_presets.canonicalization import serialize_chat_preset_sections
from core.chat_presets.identity import canonicalize_chat_preset_name, chat_preset_name_key
from core.chat_presets.stored_projection import ChatPresetStoredIntegrityError
from core.errors.exceptions import StateError
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.integers import is_positive_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.repositories.users.chat_preset_rows import (
    project_chat_preset_row,
    read_owned_chat_preset_row,
)

if TYPE_CHECKING:
    from core.chat_presets.contracts import (
        ChatPresetMutationResult,
        ChatPresetMutationStatus,
        ChatPresetProjectedRecord,
        ChatPresetSections,
    )

__all__ = (
    "sync_create_chat_preset",
    "sync_delete_chat_preset",
    "sync_rename_chat_preset",
    "sync_replace_chat_preset",
    "sync_reset_chat_presets",
)

_PRESET_LIMIT_PER_USER = 100
_ID_INSERT_ATTEMPTS = 3
_NAME_UNIQUE_ERROR = (
    "UNIQUE constraint failed: webui_chat_presets.user_id, webui_chat_presets.name_key"
)
_ID_UNIQUE_ERROR = "UNIQUE constraint failed: webui_chat_presets.id"


def _result(
    status: ChatPresetMutationStatus,
    preset: ChatPresetProjectedRecord | None = None,
) -> ChatPresetMutationResult:
    return {"status": status, "preset": preset}


def _created_timestamp() -> int:
    timestamp = int(epoch_ms())
    if timestamp < EPOCH_MS_MIN or timestamp > EPOCH_MS_MAX:
        raise StateError("Current time is outside the supported chat preset range.")
    return timestamp


def _project_success(row: JSONDict | None) -> ChatPresetMutationResult:
    if row is None:
        raise StateError("Chat preset mutation did not return its committed row.")
    try:
        projected = project_chat_preset_row(row)
    except ChatPresetStoredIntegrityError as exception:
        raise StateError("Chat preset mutation produced an invalid row.") from exception
    return _result("success", projected)


def _is_integrity_error(exception: sqlite3.IntegrityError, expected: str) -> bool:
    return str(exception) == expected


def sync_create_chat_preset(
    conn: sqlite3.Connection,
    user_id: int,
    name: str,
    sections: ChatPresetSections,
) -> ChatPresetMutationResult:
    canonical_name = canonicalize_chat_preset_name(name)
    name_key = chat_preset_name_key(canonical_name)
    sections_json = serialize_chat_preset_sections(sections)
    owner = conn.execute(
        "SELECT 1 FROM webui_users WHERE id = ? AND account_type = 'human'",
        (user_id,),
    ).fetchone()
    if owner is None:
        return _result("not_found")
    conflict = conn.execute(
        "SELECT 1 FROM webui_chat_presets WHERE user_id = ? AND name_key = ?",
        (user_id, name_key),
    ).fetchone()
    if conflict is not None:
        return _result("name_conflict")
    count_row = conn.execute(
        "SELECT count(*) FROM webui_chat_presets WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if count_row is None:
        raise StateError("Chat preset capacity query returned no row.")
    if int(count_row[0]) >= _PRESET_LIMIT_PER_USER:
        return _result("limit_reached")
    timestamp = _created_timestamp()
    for _attempt in range(_ID_INSERT_ATTEMPTS):
        preset_id = create_prefixed_hex_id("preset")
        try:
            conn.execute(
                """
                INSERT INTO webui_chat_presets (
                    id, user_id, name, name_key, sections_json, revision,
                    created_at_ms, modified_at_ms
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    preset_id,
                    user_id,
                    canonical_name,
                    name_key,
                    sections_json,
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as exception:
            if _is_integrity_error(exception, _ID_UNIQUE_ERROR):
                continue
            if _is_integrity_error(exception, _NAME_UNIQUE_ERROR):
                return _result("name_conflict")
            raise
        return _project_success(
            read_owned_chat_preset_row(conn, user_id=user_id, preset_id=preset_id),
        )
    raise StateError("Chat preset identifier allocation failed after three attempts.")


def _next_version(row: JSONDict) -> tuple[int, int] | None:
    revision = row.get("revision")
    modified_at_ms = row.get("modified_at_ms")
    if (
        not is_positive_strict_int(revision)
        or revision >= JAVASCRIPT_SAFE_INTEGER_MAX
        or not is_positive_strict_int(modified_at_ms)
        or modified_at_ms >= EPOCH_MS_MAX
    ):
        return None
    current_time = int(epoch_ms())
    next_modified_at_ms = max(current_time, modified_at_ms + 1)
    if next_modified_at_ms > EPOCH_MS_MAX:
        return None
    return revision + 1, next_modified_at_ms


def _sync_update_chat_preset(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    preset_id: str,
    expected_revision: int,
    name: str,
    replacement_sections: ChatPresetSections | None,
) -> ChatPresetMutationResult:
    row = read_owned_chat_preset_row(conn, user_id=user_id, preset_id=preset_id)
    if row is None:
        return _result("not_found")
    try:
        project_chat_preset_row(row)
    except ChatPresetStoredIntegrityError:
        return _result("corrupt_record")
    stored_revision = row["revision"]
    if stored_revision != expected_revision:
        return _result("revision_conflict")
    canonical_name = canonicalize_chat_preset_name(name)
    name_key = chat_preset_name_key(canonical_name)
    sections_json = (
        serialize_chat_preset_sections(replacement_sections)
        if replacement_sections is not None
        else row["sections_json"]
    )
    if (
        row["name"] == canonical_name
        and row["name_key"] == name_key
        and row["sections_json"] == sections_json
    ):
        return _project_success(row)
    next_version = _next_version(row)
    if next_version is None:
        return _result("revision_exhausted")
    next_revision, modified_at_ms = next_version
    try:
        conn.execute(
            """
            UPDATE webui_chat_presets
            SET name = ?, name_key = ?, sections_json = ?, revision = ?, modified_at_ms = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                canonical_name,
                name_key,
                sections_json,
                next_revision,
                modified_at_ms,
                preset_id,
                user_id,
            ),
        )
    except sqlite3.IntegrityError as exception:
        if _is_integrity_error(exception, _NAME_UNIQUE_ERROR):
            return _result("name_conflict")
        raise
    return _project_success(
        read_owned_chat_preset_row(conn, user_id=user_id, preset_id=preset_id),
    )


def sync_rename_chat_preset(
    conn: sqlite3.Connection,
    user_id: int,
    preset_id: str,
    expected_revision: int,
    name: str,
) -> ChatPresetMutationResult:
    return _sync_update_chat_preset(
        conn,
        user_id=user_id,
        preset_id=preset_id,
        expected_revision=expected_revision,
        name=name,
        replacement_sections=None,
    )


def sync_replace_chat_preset(
    conn: sqlite3.Connection,
    user_id: int,
    preset_id: str,
    expected_revision: int,
    name: str,
    sections: ChatPresetSections,
) -> ChatPresetMutationResult:
    return _sync_update_chat_preset(
        conn,
        user_id=user_id,
        preset_id=preset_id,
        expected_revision=expected_revision,
        name=name,
        replacement_sections=sections,
    )


def sync_delete_chat_preset(
    conn: sqlite3.Connection,
    user_id: int,
    preset_id: str,
    expected_revision: int,
) -> ChatPresetMutationResult:
    row = conn.execute(
        "SELECT revision FROM webui_chat_presets WHERE id = ? AND user_id = ?",
        (preset_id, user_id),
    ).fetchone()
    if row is None:
        return _result("not_found")
    revision = row["revision"]
    if not is_positive_strict_int(revision) or revision > JAVASCRIPT_SAFE_INTEGER_MAX:
        return _result("corrupt_record")
    if revision != expected_revision:
        return _result("revision_conflict")
    conn.execute(
        "DELETE FROM webui_chat_presets WHERE id = ? AND user_id = ?",
        (preset_id, user_id),
    )
    return _result("success")


def sync_reset_chat_presets(conn: sqlite3.Connection, user_id: int) -> int:
    cursor = conn.execute("DELETE FROM webui_chat_presets WHERE user_id = ?", (user_id,))
    return max(0, int(cursor.rowcount))
