"""SoAI - Skill activation persistence within fenced turn transactions [backend/database/repositories/skills/turn_checkpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.errors.exceptions import ValidationError
from core.skills.checkpoint import SkillActivationCheckpoint
from database.repositories.users.conversation_input_queries import (
    sync_require_conversation_input_claim,
)

if TYPE_CHECKING:
    from core.database.requests import ClaimAgentTurnStateRequest, WriteAgentTurnStateRequest
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "skill_read_turn_checkpoint",
    "validate_skill_turn_checkpoint",
    "write_skill_turn_checkpoint",
    "validate_skill_turn_admission",
)


def skill_read_turn_checkpoint(
    connection: sqlite3.Connection, *, user_id: int, conv_id: str, turn_id: str
) -> SkillActivationCheckpoint | None:
    row = connection.execute(
        "SELECT activation_json FROM webui_skill_turn_checkpoints WHERE user_id = ? AND conv_id = ? AND turn_id = ?",
        (user_id, conv_id, turn_id),
    ).fetchone()
    return SkillActivationCheckpoint.deserialize(row[0]) if row is not None else None


def validate_skill_turn_admission(
    connection: sqlite3.Connection, request: ClaimAgentTurnStateRequest
) -> None:
    turn = request.turn_state
    checkpoint = turn.skill_activation
    if checkpoint is None:
        return
    if turn.parent_turn_id is None:
        claim = request.skill_input_claim
        if claim is None or claim.input_id != checkpoint.snapshot_input_id:
            raise ValidationError("Skill turn admission requires its input claim.")
        sync_require_conversation_input_claim(connection, claim)
        return
    parent = connection.execute(
        """SELECT checkpoint.input_id FROM webui_agent_turns AS parent
        JOIN webui_skill_turn_checkpoints AS checkpoint
          ON checkpoint.user_id = parent.user_id AND checkpoint.conv_id = parent.conv_id
          AND checkpoint.turn_id = parent.turn_id
        WHERE parent.user_id = ? AND parent.conv_id = ? AND parent.turn_id = ?
          AND parent.status = 'running' AND parent.execution_token = ?
          AND parent.server_boot_id = ?""",
        (
            turn.user_id,
            turn.conv_id,
            turn.parent_turn_id,
            request.skill_parent_execution_token,
            turn.server_boot_id,
        ),
    ).fetchone()
    if parent is None or parent[0] != checkpoint.snapshot_input_id:
        raise ValidationError("Skill child admission requires a live parent execution.")


def validate_skill_turn_checkpoint(
    connection: sqlite3.Connection,
    request: WriteAgentTurnStateRequest,
    existing_turn: SQLiteRowDict | None,
) -> None:
    proposed = request.skill_activation
    if proposed is None:
        return
    previous = skill_read_turn_checkpoint(
        connection, user_id=request.user_id, conv_id=request.conv_id, turn_id=request.turn_id
    )
    if existing_turn is not None and previous is None:
        raise ValidationError("Skill authority must be attached when the turn is admitted.")
    if previous is not None:
        if proposed.snapshot_input_id != previous.snapshot_input_id:
            raise ValidationError("Skill activation cannot change its admitted input.")
        if proposed.active_skills[: len(previous.active_skills)] != previous.active_skills:
            raise ValidationError("Committed skill activations cannot be removed or reordered.")
        if proposed.invocations[: len(previous.invocations)] != previous.invocations:
            raise ValidationError(
                "Committed skill invocation bindings cannot be replaced or reordered."
            )
        if proposed != previous and request.parent_turn_id is None:
            claim = request.skill_input_claim
            if claim is None or claim.input_id != proposed.snapshot_input_id:
                raise ValidationError("Skill activation requires its current input claim.")
            sync_require_conversation_input_claim(connection, claim)
    if existing_turn is not None and existing_turn.get("status") != AGENT_TURN_STATUS_RUNNING:
        if proposed != previous:
            raise ValidationError("A completed turn cannot change skill activation.")
    snapshot = connection.execute(
        "SELECT 1 FROM webui_skill_snapshots WHERE user_id = ? AND conv_id = ? AND input_id = ?",
        (request.user_id, request.conv_id, proposed.snapshot_input_id),
    ).fetchone()
    if snapshot is None:
        raise ValidationError("Skill activation requires an owned admitted input.")
    rows = connection.execute(
        """SELECT membership.skill_id, membership.package_digest,
            membership.explicit_ordinal, skill.disable_model_invocation,
            skill.package_digest, membership.profile_digest, skill.profile_digest, membership.invocation_arguments
        FROM webui_skill_snapshot_members AS membership
        JOIN webui_skills AS skill ON skill.user_id = membership.user_id
          AND skill.skill_id = membership.skill_id
        WHERE membership.user_id = ? AND membership.conv_id = ? AND membership.input_id = ?""",
        (request.user_id, request.conv_id, proposed.snapshot_input_id),
    ).fetchall()
    available = {row[0]: row for row in rows}
    for skill_id, digest in proposed.active_skills:
        member = available.get(skill_id)
        if member is None or digest != member[1] or digest != member[4]:
            raise ValidationError("Skill activation differs from admitted package identity.")
        if member[5] != member[6]:
            raise ValidationError(
                "Skill activation differs from its admitted compatibility profile."
            )
        if member[3] and member[2] is None:
            raise ValidationError("Skill activation requires an admitted human invocation.")
    for invocation in proposed.invocations:
        member = available.get(invocation.skill_id)
        if member is None or (member[7] is not None and member[7] != invocation.arguments):
            raise ValidationError(
                "Skill invocation differs from its admitted human argument binding."
            )


def write_skill_turn_checkpoint(
    connection: sqlite3.Connection, request: WriteAgentTurnStateRequest
) -> None:
    checkpoint = request.skill_activation
    if checkpoint is None:
        return
    connection.execute(
        """INSERT INTO webui_skill_turn_checkpoints
            (user_id, conv_id, turn_id, input_id, activation_json) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(conv_id, user_id, turn_id) DO UPDATE SET activation_json = excluded.activation_json""",
        (
            request.user_id,
            request.conv_id,
            request.turn_id,
            checkpoint.snapshot_input_id,
            checkpoint.serialize(),
        ),
    )
