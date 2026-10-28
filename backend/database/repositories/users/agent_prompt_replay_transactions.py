"""SoAI - Atomic agent prompt replay persistence [backend/database/repositories/users/agent_prompt_replay_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.agent_tool_messages import build_assistant_tool_message
from core.serialization.json import normalize_for_json, serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.types.json_value import require_json_dict_list
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.skills.turn_checkpoints import skill_read_turn_checkpoint
from database.repositories.users.agent_turn_rows import format_agent_turn_row

if TYPE_CHECKING:
    from core.database.requests import ClaimAgentTurnStateRequest, WriteAgentTurnStateRequest
    from core.skills.checkpoint import SkillActivationCheckpoint
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "serialize_replay_checkpoint",
    "sync_validate_replay_snapshot",
    "sync_write_prompt_replay",
)


def serialize_replay_checkpoint(
    *, row: SQLiteRowDict, skill_activation: SkillActivationCheckpoint | None = None
) -> str:
    checkpoint = format_agent_turn_row(row)
    if checkpoint is None:
        raise ValidationError("Agent replay checkpoint is unavailable.")
    checkpoint["prompt_replay_start_iteration"] = normalize_for_json(
        row.get("prompt_replay_start_iteration"),
    )
    if skill_activation is not None:
        checkpoint["skill_activation"] = skill_activation.serialize()
    return serialize_json_compact_stable(checkpoint)


def sync_validate_replay_snapshot(
    sqlite_conn: sqlite3.Connection,
    *,
    request: ClaimAgentTurnStateRequest,
) -> None:
    snapshot = request.prompt_replay_snapshot
    if snapshot is None:
        return
    turn = request.turn_state
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT * FROM webui_agent_turns WHERE conv_id = ? AND user_id = ? AND turn_id = ?",
            (turn.conv_id, turn.user_id, turn.turn_id),
        )
    )
    skill_activation = skill_read_turn_checkpoint(
        sqlite_conn, user_id=turn.user_id, conv_id=turn.conv_id, turn_id=turn.turn_id
    )
    if (
        row is None
        or serialize_replay_checkpoint(row=row, skill_activation=skill_activation)
        != snapshot.checkpoint_json
    ):
        raise ValidationError("Agent replay checkpoint changed before resume.")
    if skill_activation != snapshot.skill_activation:
        raise ValidationError("Agent skill activation changed before resume.")
    if turn.execution_token == row.get("execution_token"):
        raise ValidationError("Agent replay resume requires a fresh execution token.")
    latest = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT * FROM webui_agent_prompt_replay WHERE conv_id = ? AND user_id = ? AND turn_id = ? ORDER BY iteration_index DESC LIMIT 1",
            (turn.conv_id, turn.user_id, turn.turn_id),
        )
    )
    serialized = serialize_json_compact_stable(normalize_for_json(latest)) if latest else None
    if serialized != snapshot.latest_replay_json:
        raise ValidationError("Agent replay history changed before resume.")


def sync_write_prompt_replay(
    sqlite_conn: sqlite3.Connection,
    *,
    request: WriteAgentTurnStateRequest,
) -> None:
    replay = request.prompt_replay
    if replay is None:
        return
    if replay.assistant_tool_message_json is not None:
        captured = parse_json_dict(
            replay.assistant_tool_message_json, field="agent replay assistant"
        )
        tool_calls = require_json_dict_list(
            parse_json_value(request.tool_calls_json, field="agent checkpoint calls"),
            label="Agent checkpoint calls",
        )
        expected = build_assistant_tool_message(
            tool_calls=tool_calls, content=request.assistant_text or ""
        )
        if captured.get("tool_calls") != expected.get("tool_calls") or captured.get(
            "content"
        ) != expected.get("content"):
            raise ValidationError("Agent replay assistant does not match its checkpoint.")
    scope = (request.conv_id, request.user_id, request.turn_id, request.iteration_index)
    existing = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT assistant_tool_message_json, following_messages_json FROM webui_agent_prompt_replay WHERE conv_id = ? AND user_id = ? AND turn_id = ? AND iteration_index = ?",
            scope,
        )
    )
    if existing is None:
        sqlite_conn.execute(
            "INSERT INTO webui_agent_prompt_replay (conv_id, user_id, turn_id, iteration_index, append_sequence, assistant_tool_message_json, following_messages_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                *scope,
                request.sequence,
                replay.assistant_tool_message_json,
                replay.following_messages_json,
            ),
        )
        return
    if existing["assistant_tool_message_json"] != replay.assistant_tool_message_json:
        raise ValidationError("Agent replay assistant message is immutable.")
    following = existing["following_messages_json"]
    if following is not None:
        if replay.following_messages_json != following:
            raise ValidationError("Completed agent replay messages are immutable.")
        return
    if replay.following_messages_json is not None:
        sqlite_conn.execute(
            "UPDATE webui_agent_prompt_replay SET following_messages_json = ?, append_sequence = ? WHERE conv_id = ? AND user_id = ? AND turn_id = ? AND iteration_index = ?",
            (replay.following_messages_json, request.sequence, *scope),
        )
