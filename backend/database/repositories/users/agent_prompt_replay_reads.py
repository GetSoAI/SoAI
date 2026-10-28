"""SoAI - Active turn prompt replay snapshots [backend/database/repositories/users/agent_prompt_replay_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import aiosqlite

from core.agent.prompt_replay import AgentInferencePromptReplay, AgentTurnPromptReplaySnapshot
from core.errors.exceptions import ValidationError
from core.openai.stream_transcript.payload_segments import extract_reasoning_text_from_source
from core.serialization.json import normalize_for_json, serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.skills.checkpoint import SkillActivationCheckpoint
from core.types.json import JSONDict
from core.types.json_value import require_json_dict_list
from core.validation.integers import is_strict_int
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.read_transaction import run_read_transaction
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.users.agent_prompt_replay_transactions import serialize_replay_checkpoint
from database.repositories.users.assistant_turn_history_projection import (
    project_assistant_turn_history_messages,
)
from database.repositories.users.canonical_agent_history_reads import query_canonical_agent_history
from database.repositories.users.prompt_compaction_projection import (
    build_prompt_compaction_marker_projections,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import AssistantTurnVariantIdentity

__all__ = ("query_agent_prompt_replay_snapshot", "read_agent_prompt_replay_snapshot")


async def query_agent_prompt_replay_snapshot(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    input_id: str,
    identity: AssistantTurnVariantIdentity,
) -> AgentTurnPromptReplaySnapshot:
    turn = await query_one_to_dict(
        database,
        "SELECT agent_turns.* FROM webui_agent_turns AS agent_turns JOIN webui_conversation_inputs AS inputs ON inputs.conv_id = agent_turns.conv_id AND inputs.user_id = agent_turns.user_id AND inputs.agent_turn_id = agent_turns.turn_id WHERE agent_turns.conv_id = ? AND agent_turns.user_id = ? AND agent_turns.turn_id = ? AND agent_turns.status = 'running' AND inputs.state IN ('materializing', 'running', 'input_required') AND inputs.input_id = ? AND inputs.assistant_at_ms = ? AND inputs.assistant_turn_at_ms = ? AND inputs.model_variant_index = ?",
        (
            conv_id,
            user_id,
            turn_id,
            input_id,
            identity.assistant_at_ms,
            identity.assistant_turn_at_ms,
            identity.model_variant_index,
        ),
    )
    if turn is None:
        raise ValidationError("Active agent replay turn is unavailable.")
    iteration = coerce_int_from_sqlite(turn.get("iteration_index"))
    floor = coerce_int_from_sqlite(turn.get("prompt_replay_start_iteration"))
    if iteration is None or floor is None or iteration < 0 or floor < 0:
        raise ValidationError("Agent replay iteration is invalid.")
    rows = await query_to_dicts(
        database,
        "SELECT * FROM webui_agent_prompt_replay WHERE conv_id = ? AND user_id = ? AND turn_id = ? ORDER BY iteration_index ASC",
        (conv_id, user_id, turn_id),
    )
    history = await query_canonical_agent_history(
        database,
        conv_id=conv_id,
        before_timestamp_exclusive=identity.assistant_turn_at_ms,
    )
    entries: list[tuple[int, int, int, list[JSONDict]]] = []
    captured: set[int] = set()
    pending_reasoning = ""
    for row in rows:
        row_iteration = coerce_int_from_sqlite(row.get("iteration_index"))
        sequence = coerce_int_from_sqlite(row.get("append_sequence"))
        if row_iteration is None or sequence is None or row_iteration > iteration:
            raise ValidationError("Agent replay chronology is invalid.")
        assistant_json = row.get("assistant_tool_message_json")
        following_json = row.get("following_messages_json")
        if (assistant_json is not None and not isinstance(assistant_json, str)) or (
            following_json is not None and not isinstance(following_json, str)
        ):
            raise ValidationError("Agent replay messages are invalid.")
        replay = AgentInferencePromptReplay(
            assistant_tool_message_json=assistant_json, following_messages_json=following_json
        )
        captured.add(row_iteration)
        assistant = (
            parse_json_dict(assistant_json, field="agent replay assistant")
            if assistant_json is not None
            else None
        )
        if replay.following_messages_json is None:
            if row_iteration != iteration or assistant is None:
                raise ValidationError("Earlier agent replay batch is incomplete.")
            pending_reasoning = extract_reasoning_text_from_source(assistant)
            continue
        messages = require_json_dict_list(
            parse_json_value(
                replay.following_messages_json, field="agent replay following messages"
            ),
            label="Agent replay following messages",
        )
        if assistant is not None:
            messages.insert(0, assistant)
        for message in messages:
            message["assistant_turn_at_ms"] = identity.assistant_turn_at_ms
            message["model_variant_index"] = identity.model_variant_index
        entries.append((sequence, 1, row_iteration, messages))
    if any(index not in captured for index in range(floor, iteration + 1)):
        raise ValidationError("Agent replay history is incomplete.")
    tool_rows = await query_to_dicts(
        database,
        "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND turn_id = ? AND assistant_at_ms = ? AND assistant_turn_at_ms = ? AND model_variant_index = ? ORDER BY sequence_index ASC",
        (
            conv_id,
            turn_id,
            identity.assistant_at_ms,
            identity.assistant_turn_at_ms,
            identity.model_variant_index,
        ),
    )
    tools = [formatted for row in tool_rows if (formatted := format_tool_call_row(row))]
    legacy: list[JSONDict] = []
    for tool in tools:
        tool_iteration = tool.get("iteration_index")
        if (
            is_strict_int(tool_iteration)
            and tool_iteration not in captured
            and tool_iteration < iteration
        ):
            legacy.append(tool)
    if legacy:
        history.extend(
            project_assistant_turn_history_messages(
                message_payload={
                    "role": "assistant",
                    "content": "",
                    "timestamp": identity.assistant_at_ms,
                },
                anchored_tool_calls=legacy,
            )
        )
    events = await query_to_dicts(
        database,
        "SELECT assistant_at_ms, sequence, assistant_revision, event_type, payload_json FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ? AND event_type = 'tool_call_completed' ORDER BY sequence ASC, assistant_revision ASC",
        (conv_id, identity.assistant_at_ms),
    )
    projections = build_prompt_compaction_marker_projections(
        tool_call_rows=tools, assistant_event_rows=events
    )
    for projection in projections:
        entries.append(
            (
                projection.event_sequence,
                0,
                0,
                [{"role": "assistant", "content": "", "soai_compaction": projection.marker}],
            )
        )
    for _, _, _, messages in sorted(entries, key=lambda entry: entry[:3]):
        history.extend(messages)
    latest_json = serialize_json_compact_stable(normalize_for_json(rows[-1])) if rows else None
    skill_row = await query_one_to_dict(
        database,
        "SELECT activation_json FROM webui_skill_turn_checkpoints WHERE user_id = ? AND conv_id = ? AND turn_id = ?",
        (user_id, conv_id, turn_id),
    )
    skill_activation = None
    if skill_row is not None:
        activation_json = skill_row["activation_json"]
        if not isinstance(activation_json, str):
            raise ValidationError("Agent skill activation checkpoint is invalid.")
        skill_activation = SkillActivationCheckpoint.deserialize(activation_json)
    return AgentTurnPromptReplaySnapshot(
        checkpoint_json=serialize_replay_checkpoint(row=turn, skill_activation=skill_activation),
        latest_replay_json=latest_json,
        history_messages_json=serialize_json_compact_stable(history),
        pending_reasoning_text=pending_reasoning,
        identity=identity,
        skill_activation=skill_activation,
    )


async def read_agent_prompt_replay_snapshot(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    input_id: str,
    identity: AssistantTurnVariantIdentity,
) -> AgentTurnPromptReplaySnapshot:
    query = partial(
        query_agent_prompt_replay_snapshot,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        input_id=input_id,
        identity=identity,
    )
    return await run_read_transaction(database, query)
