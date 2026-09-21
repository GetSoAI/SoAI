"""SoAI - Database schema: conversation inputs [backend/database/schema_scripts/conversation_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_conversation_inputs_schema",)


def build_conversation_inputs_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_conversation_inputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_id TEXT NOT NULL UNIQUE,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            input_type TEXT NOT NULL CHECK(input_type IN ('prompt', 'steer', 'control')),
            transport_origin TEXT NOT NULL CHECK(transport_origin IN ('chat', 'messaging')),
            text TEXT NOT NULL DEFAULT '',
            attachment_content_json TEXT NOT NULL DEFAULT '[]'
                CHECK(json_valid(attachment_content_json) AND json_type(attachment_content_json)='array'),
            model_settings_json TEXT
                CHECK(model_settings_json IS NULL OR (json_valid(model_settings_json) AND json_type(model_settings_json)='object')),
            source_key TEXT NOT NULL CHECK(length(trim(source_key)) > 0),
            content_fingerprint TEXT NOT NULL CHECK(length(content_fingerprint) = 64),
            prompt_history_fingerprint TEXT
                CHECK(prompt_history_fingerprint IS NULL OR (
                    length(prompt_history_fingerprint) = 64
                    AND prompt_history_fingerprint = lower(prompt_history_fingerprint)
                    AND prompt_history_fingerprint NOT GLOB '*[^0-9a-f]*'
                )),
            client_id TEXT,
            client_request_id TEXT,
            messaging_ingress_id TEXT,
            source_metadata_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK(json_valid(source_metadata_json) AND json_type(source_metadata_json)='object'),
            media_descriptors_json TEXT NOT NULL DEFAULT '[]'
                CHECK(json_valid(media_descriptors_json) AND json_type(media_descriptors_json)='array'),
            state TEXT NOT NULL CHECK(state IN (
                'pending', 'materializing', 'running', 'input_required',
                'completed', 'failed', 'cancelled', 'effect_unknown'
            )),
            conversation_generation INTEGER NOT NULL CHECK(conversation_generation >= 0),
            claim_generation INTEGER NOT NULL DEFAULT 0 CHECK(claim_generation >= 0),
            claim_owner TEXT,
            claim_server_boot_id TEXT,
            target_input_id TEXT,
            materialized_message_id INTEGER,
            materialized_message_at_ms INTEGER
                CHECK(materialized_message_at_ms IS NULL OR materialized_message_at_ms >= {EPOCH_MS_MIN}),
            request_id TEXT,
            assistant_at_ms INTEGER CHECK(assistant_at_ms IS NULL OR assistant_at_ms >= {EPOCH_MS_MIN}),
            assistant_turn_at_ms INTEGER
                CHECK(assistant_turn_at_ms IS NULL OR assistant_turn_at_ms >= {EPOCH_MS_MIN}),
            model_variant_index INTEGER CHECK(model_variant_index IS NULL OR model_variant_index >= 0),
            agent_turn_id TEXT,
            task_id TEXT,
            suspension_phase TEXT CHECK(suspension_phase IS NULL OR suspension_phase IN (
                'before_approved_tool', 'awaiting_ask_user_result', 'awaiting_vault_secret'
            )),
            suspension_iteration INTEGER CHECK(suspension_iteration IS NULL OR suspension_iteration >= 0),
            suspension_tool_call_id TEXT,
            suspension_generation INTEGER CHECK(suspension_generation IS NULL OR suspension_generation >= 0),
            terminal_code TEXT,
            terminal_args_json TEXT
                CHECK(terminal_args_json IS NULL OR (json_valid(terminal_args_json) AND json_type(terminal_args_json)='object')),
            accepted_at_ms INTEGER NOT NULL CHECK(accepted_at_ms >= {EPOCH_MS_MIN}),
            claimed_at_ms INTEGER CHECK(claimed_at_ms IS NULL OR claimed_at_ms >= {EPOCH_MS_MIN}),
            materialized_at_ms INTEGER CHECK(materialized_at_ms IS NULL OR materialized_at_ms >= {EPOCH_MS_MIN}),
            running_at_ms INTEGER CHECK(running_at_ms IS NULL OR running_at_ms >= {EPOCH_MS_MIN}),
            input_required_at_ms INTEGER
                CHECK(input_required_at_ms IS NULL OR input_required_at_ms >= {EPOCH_MS_MIN}),
            terminal_at_ms INTEGER CHECK(terminal_at_ms IS NULL OR terminal_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            regeneration_request_json TEXT
                CHECK(regeneration_request_json IS NULL OR (
                    json_valid(regeneration_request_json)
                    AND json_type(regeneration_request_json)='object'
                )),
            regeneration_accepted_revision INTEGER
                CHECK(regeneration_accepted_revision IS NULL OR regeneration_accepted_revision >= {EPOCH_MS_MIN})
                CHECK((regeneration_request_json IS NULL) = (regeneration_accepted_revision IS NULL)),
            CHECK(input_type != 'prompt' OR model_settings_json IS NOT NULL),
            CHECK(input_type = 'prompt' OR model_settings_json IS NULL),
            CHECK(transport_origin != 'chat' OR (client_id IS NOT NULL AND messaging_ingress_id IS NULL)),
            CHECK(transport_origin != 'messaging' OR (messaging_ingress_id IS NOT NULL AND client_id IS NULL)),
            CHECK(input_type != 'steer' OR target_input_id IS NOT NULL),
            CHECK(input_type = 'steer' OR target_input_id IS NULL),
            CHECK(state NOT IN ('materializing', 'running', 'input_required') OR (
                claim_owner IS NOT NULL AND claim_server_boot_id IS NOT NULL
                AND claimed_at_ms IS NOT NULL AND claim_generation > 0
            )),
            CHECK(state != 'materializing' OR materialized_message_id IS NULL),
            CHECK(state NOT IN ('running', 'input_required') OR materialized_message_id IS NOT NULL),
            CHECK(state NOT IN ('completed', 'failed', 'cancelled', 'effect_unknown') OR (
                terminal_code IS NOT NULL AND terminal_args_json IS NOT NULL
                AND terminal_at_ms IS NOT NULL
            )),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(target_input_id) REFERENCES webui_conversation_inputs(input_id) ON DELETE RESTRICT,
            FOREIGN KEY(materialized_message_id) REFERENCES webui_messages(id) ON DELETE SET NULL,
            UNIQUE(user_id, transport_origin, source_key)
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_conversation_inputs_dispatch
            ON webui_conversation_inputs(state, accepted_at_ms, id);
        CREATE INDEX IF NOT EXISTS idx_conversation_inputs_head
            ON webui_conversation_inputs(conv_id, accepted_at_ms, id, state);
        CREATE INDEX IF NOT EXISTS idx_conversation_inputs_owner
            ON webui_conversation_inputs(user_id, conv_id, accepted_at_ms DESC, id DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_inputs_materialized_message
            ON webui_conversation_inputs(materialized_message_id)
            WHERE materialized_message_id IS NOT NULL AND regeneration_request_json IS NULL;
        CREATE INDEX IF NOT EXISTS idx_conversation_inputs_claim
            ON webui_conversation_inputs(claim_server_boot_id, claim_owner, state);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_inputs_one_executing
            ON webui_conversation_inputs(conv_id)
            WHERE state IN ('materializing', 'running', 'input_required');
        """


def apply_conversation_inputs_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_conversation_inputs_schema_sql())
