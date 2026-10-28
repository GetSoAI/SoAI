"""SoAI - Skill content consumer retention and library revisions [backend/database/repositories/skills/retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.errors.exceptions import StateError
from core.events.domain_event_payload import build_domain_event_payload
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload
from database.repositories.users.conversation_input_constants import TERMINAL_INPUT_STATES

__all__ = (
    "sync_reconcile_skill_retention",
    "sync_reconcile_all_skill_retention",
    "sync_reclaim_skill_content",
)


def sync_reclaim_skill_content(connection: sqlite3.Connection, user_id: int) -> bool:
    terminal_states = tuple(sorted(TERMINAL_INPUT_STATES))
    placeholders = ", ".join("?" for _ in terminal_states)
    reclaimed = connection.execute(
        f"""UPDATE webui_skills AS skill SET manifest_json = '{{}}', profile_json = '{{}}'
        WHERE skill.user_id = ? AND skill.removed_at_ms IS NOT NULL
          AND skill.manifest_json != '{{}}'
          AND NOT EXISTS (
            SELECT 1 FROM webui_skill_materializations AS materialization
            WHERE materialization.user_id = skill.user_id AND materialization.skill_id = skill.skill_id
              AND materialization.terminal_status IS NULL
          )
          AND NOT EXISTS (
            SELECT 1 FROM webui_skill_snapshot_members AS membership
            JOIN webui_conversation_inputs AS input
              ON input.user_id = membership.user_id AND input.conv_id = membership.conv_id
              AND input.input_id = membership.input_id
            WHERE membership.user_id = skill.user_id AND membership.skill_id = skill.skill_id
              AND (input.state NOT IN ({placeholders}) OR EXISTS (
                SELECT 1 FROM webui_skill_turn_checkpoints AS checkpoint
                JOIN webui_agent_turns AS turn
                  ON turn.user_id = checkpoint.user_id AND turn.conv_id = checkpoint.conv_id
                  AND turn.turn_id = checkpoint.turn_id
                WHERE checkpoint.user_id = membership.user_id
                  AND checkpoint.conv_id = membership.conv_id
                  AND checkpoint.input_id = membership.input_id AND turn.status = ?
              ))
          ) RETURNING skill_id""",
        (user_id, *terminal_states, AGENT_TURN_STATUS_RUNNING),
    ).fetchall()
    connection.executemany(
        "DELETE FROM webui_skill_members WHERE user_id = ? AND skill_id = ?",
        [(user_id, row[0]) for row in reclaimed],
    )
    connection.executemany(
        "DELETE FROM webui_skill_support_bindings WHERE user_id=? AND skill_id=?",
        [(user_id, row[0]) for row in reclaimed],
    )
    connection.execute(
        """DELETE FROM webui_skill_supporting_members AS support WHERE user_id=? AND NOT EXISTS (SELECT 1 FROM webui_skill_support_bindings AS binding WHERE binding.user_id=support.user_id AND binding.upload_id=support.upload_id AND binding.path=support.path)""",
        (user_id,),
    )
    return bool(reclaimed)


def sync_reconcile_skill_retention(
    connection: sqlite3.Connection, user_id: int, timestamp: int, *, library_changed: bool = False
) -> int:
    reclaimed = sync_reclaim_skill_content(connection, user_id)
    if not reclaimed and not library_changed:
        current = connection.execute(
            "SELECT revision FROM webui_skill_libraries WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(current[0]) if current is not None else 0
    connection.execute(
        "INSERT INTO webui_skill_libraries (user_id, revision) VALUES (?, 0) ON CONFLICT DO NOTHING",
        (user_id,),
    )
    row = connection.execute(
        """UPDATE webui_skill_libraries SET revision = revision + 1
        WHERE user_id = ? AND revision < ? RETURNING revision""",
        (user_id, JAVASCRIPT_SAFE_INTEGER_MAX),
    ).fetchone()
    if row is None:
        raise StateError("Skill library revision is exhausted.")
    revision = int(row[0])
    sync_enqueue_domain_event_payload(
        connection,
        event_type="SkillLibraryChangedEvent",
        created_at_ms=timestamp,
        payload=build_domain_event_payload(fields={"user_id": user_id, "revision": revision}),
    )
    return revision


def sync_reconcile_all_skill_retention(connection: sqlite3.Connection, timestamp: int) -> None:
    owners = connection.execute(
        "SELECT DISTINCT user_id FROM webui_skills WHERE removed_at_ms IS NOT NULL AND manifest_json != '{}'"
    ).fetchall()
    for owner in owners:
        sync_reconcile_skill_retention(connection, int(owner[0]), timestamp)
