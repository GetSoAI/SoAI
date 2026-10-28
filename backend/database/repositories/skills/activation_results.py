"""SoAI - Atomic skill activation tool result publication [backend/database/repositories/skills/activation_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.database.requests import WriteAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from database.repositories.users.tool_call_state_transactions import (
    sync_finalize_active_tool_call_with_result,
)

__all__ = ("sync_commit_skill_activation_result",)


def sync_commit_skill_activation_result(
    connection: sqlite3.Connection, request: WriteAgentTurnStateRequest
) -> None:
    call_id = request.skill_activation_call_id
    if call_id is None:
        return
    checkpoint = request.skill_activation
    calls = parse_json_value(request.tool_calls_json, field="skill activation calls")
    results = parse_json_value(request.tool_results_json, field="skill activation results")
    if checkpoint is None or not isinstance(calls, list) or not isinstance(results, list):
        raise ValidationError("Skill activation result requires its checkpoint and tool progress.")
    if not results or len(results) > len(calls):
        raise ValidationError("Skill activation result is outside the tool call sequence.")
    call = calls[len(results) - 1]
    result = results[-1]
    if not isinstance(call, dict) or call.get("id") != call_id or call.get("name") != "skill_read":
        raise ValidationError("Skill activation result differs from its tool call.")
    if not isinstance(result, dict) or result.get("activated") is not True:
        raise ValidationError("Skill activation result must confirm successful activation.")
    skill_id = result.get("skill_id")
    if not isinstance(skill_id, str) or skill_id not in {
        identity for identity, _digest in checkpoint.active_skills
    }:
        raise ValidationError("Skill activation result differs from its committed authority.")
    if request.turn_scope == TURN_SCOPE_SUBAGENT:
        return
    rows = connection.execute(
        """SELECT id, status, tool_result, started_at_ms, created_at_ms
        FROM webui_chat_tool_calls WHERE conv_id = ? AND turn_id = ?
        AND iteration_index = ? AND call_id = ? AND tool_name = 'skill_read'""",
        (request.conv_id, request.turn_id, request.iteration_index, call_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValidationError("Skill activation requires one owned visible tool call.")
    row = rows[0]
    serialized_result = serialize_json_compact_stable(result)
    if row[1] == "completed" and row[2] == serialized_result:
        return
    if row[1] not in ("pending", "running"):
        raise ValidationError("Skill activation tool call was already settled differently.")
    started = row[3] if row[3] is not None else row[4]
    sync_finalize_active_tool_call_with_result(
        connection,
        row[0],
        "completed",
        serialized_result,
        None,
        max(0, request.updated_at_ms - started),
        max(request.updated_at_ms, started),
    )
