"""SoAI - Durable agent prompt replay schema [backend/database/schema_scripts/agent_prompt_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("AGENT_PROMPT_REPLAY_SCHEMA_V4",)

AGENT_PROMPT_REPLAY_SCHEMA_V4: str = """
    CREATE TABLE IF NOT EXISTS webui_agent_prompt_replay (
        conv_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        turn_id TEXT NOT NULL,
        iteration_index INTEGER NOT NULL CHECK(iteration_index >= 0),
        append_sequence INTEGER NOT NULL CHECK(append_sequence >= 0),
        assistant_tool_message_json TEXT CHECK(assistant_tool_message_json IS NULL OR
            (json_valid(assistant_tool_message_json) AND json_type(assistant_tool_message_json) = 'object')),
        following_messages_json TEXT CHECK(following_messages_json IS NULL OR
            (json_valid(following_messages_json) AND json_type(following_messages_json) = 'array')),
        CHECK(assistant_tool_message_json IS NOT NULL OR following_messages_json IS NOT NULL),
        PRIMARY KEY(conv_id, user_id, turn_id, iteration_index),
        FOREIGN KEY(conv_id, user_id, turn_id)
            REFERENCES webui_agent_turns(conv_id, user_id, turn_id) ON DELETE CASCADE
    ) WITHOUT ROWID, STRICT;
"""
