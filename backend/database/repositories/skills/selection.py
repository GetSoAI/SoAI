"""SoAI - Revision fenced conversation skill selection transactions [backend/database/repositories/skills/selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.settings_authority import resolve_conversation_settings_authority
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.skills.selection import (
    canonicalize_skill_selection,
    require_skill_id,
    require_skill_revision,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload
from database.repositories.skills.library import require_skill_library_owner
from database.repositories.skills.retention import (
    sync_reconcile_skill_retention,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_sync_operations import sync_get_conversation

__all__ = (
    "sync_get_skill_selection",
    "sync_replace_skill_selection",
    "sync_advance_skill_selection",
    "sync_remove_skill",
)


def sync_get_skill_selection(
    connection: sqlite3.Connection, user_id: int, conv_id: str
) -> JSONDict:
    ensure_conversation_owned(connection, conv_id, user_id)
    revision = connection.execute(
        "SELECT revision FROM webui_conversation_skill_state WHERE user_id = ? AND conv_id = ?",
        (user_id, conv_id),
    ).fetchone()
    selected = connection.execute(
        "SELECT skill_id FROM webui_conversation_skills WHERE user_id = ? AND conv_id = ? ORDER BY skill_id",
        (user_id, conv_id),
    ).fetchall()
    return {
        "conv_id": conv_id,
        "revision": int(revision[0]) if revision else 0,
        "skill_ids": [str(row[0]) for row in selected],
    }


def sync_replace_skill_selection(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    expected_revision: int,
    skill_ids: tuple[str, ...],
) -> JSONDict:
    require_skill_library_owner(connection, user_id)
    revision = require_skill_revision(expected_revision)
    selected = canonicalize_skill_selection(list(skill_ids))
    conversation = sync_get_conversation(connection, conv_id, user_id)
    if conversation is None:
        raise ValidationError("Conversation not found or access denied.")
    if resolve_conversation_settings_authority(conversation).is_read_only:
        raise ValidationError("Skills can be selected only in ordinary conversations.")
    current = sync_get_skill_selection(connection, user_id, conv_id)
    if current["revision"] != revision:
        raise ConflictError(
            "Skill selection changed. Review the current selection before saving.", details=current
        )
    for skill_id in selected:
        if (
            connection.execute(
                """SELECT 1 FROM webui_skills WHERE user_id = ? AND skill_id = ?
            AND removed_at_ms IS NULL AND (disable_model_invocation = 0 OR user_invocable = 1)""",
                (user_id, skill_id),
            ).fetchone()
            is None
        ):
            raise ValidationError(
                "A selected skill is removed, unavailable or belongs to another account."
            )
    if current["skill_ids"] == list(selected):
        return current
    connection.execute(
        """INSERT INTO webui_conversation_skill_state (user_id, conv_id, revision)
        VALUES (?, ?, 0) ON CONFLICT DO NOTHING""",
        (user_id, conv_id),
    )
    connection.execute(
        "DELETE FROM webui_conversation_skills WHERE user_id = ? AND conv_id = ?",
        (user_id, conv_id),
    )
    connection.executemany(
        "INSERT INTO webui_conversation_skills (user_id, conv_id, skill_id) VALUES (?, ?, ?)",
        [(user_id, conv_id, skill_id) for skill_id in selected],
    )
    sync_advance_skill_selection(connection, user_id, conv_id, epoch_ms())
    return sync_get_skill_selection(connection, user_id, conv_id)


def sync_advance_skill_selection(
    connection: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    timestamp: int,
) -> None:
    row = connection.execute(
        """UPDATE webui_conversation_skill_state SET revision = revision + 1
        WHERE user_id = ? AND conv_id = ? AND revision < ? RETURNING revision""",
        (user_id, conv_id, JAVASCRIPT_SAFE_INTEGER_MAX),
    ).fetchone()
    if row is None:
        raise StateError("Skill selection revision is missing or exhausted.")
    sync_enqueue_domain_event_payload(
        connection,
        event_type="ConversationSkillsChangedEvent",
        created_at_ms=timestamp,
        payload=build_domain_event_payload(
            fields={"user_id": user_id, "conv_id": conv_id, "revision": int(row[0])}
        ),
    )


def sync_remove_skill(connection: sqlite3.Connection, user_id: int, skill_id: str) -> JSONDict:
    require_skill_library_owner(connection, user_id)
    require_skill_id(skill_id)
    timestamp = epoch_ms()
    row = connection.execute(
        """UPDATE webui_skills SET removed_at_ms = max(created_at_ms, ?)
        WHERE user_id = ? AND skill_id = ? AND removed_at_ms IS NULL RETURNING skill_id""",
        (timestamp, user_id, skill_id),
    ).fetchone()
    if row is not None:
        conversations = connection.execute(
            "SELECT conv_id FROM webui_conversation_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, skill_id),
        ).fetchall()
        connection.execute(
            "DELETE FROM webui_conversation_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, skill_id),
        )
        for conversation in conversations:
            sync_advance_skill_selection(connection, user_id, str(conversation[0]), timestamp)
        revision = sync_reconcile_skill_retention(
            connection, user_id, timestamp, library_changed=True
        )
    else:
        existing = connection.execute(
            "SELECT revision FROM webui_skill_libraries WHERE user_id = ?", (user_id,)
        ).fetchone()
        revision = int(existing[0]) if existing else 0
    return {"removed": True, "revision": revision}
