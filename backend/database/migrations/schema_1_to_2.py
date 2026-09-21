"""SoAI - Database schema migration from 1 to 2 [backend/database/migrations/schema_1_to_2.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.sql.script import execute_sql_script

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("migrate_database_schema_1_to_2",)


def migrate_database_schema_1_to_2(
    connection: sqlite3.Connection,
    logger: LoggerProtocol,
) -> None:
    del logger
    execute_sql_script(
        connection,
        """
        ALTER TABLE hardware_gpu_soaibench_runs
            ADD COLUMN publication_source_supported INTEGER NOT NULL DEFAULT 0
            CHECK(publication_source_supported IN (0, 1));
        ALTER TABLE webui_conversation_inputs
            ADD COLUMN regeneration_request_json TEXT
            CHECK(regeneration_request_json IS NULL OR (
                json_valid(regeneration_request_json)
                AND json_type(regeneration_request_json)='object'
            ));
        ALTER TABLE webui_conversation_inputs
            ADD COLUMN regeneration_accepted_revision INTEGER
            CHECK(regeneration_accepted_revision IS NULL OR regeneration_accepted_revision >= 1000000000000)
            CHECK((regeneration_request_json IS NULL) = (regeneration_accepted_revision IS NULL));
        DROP INDEX idx_conversation_inputs_materialized_message;
        CREATE UNIQUE INDEX idx_conversation_inputs_materialized_message
            ON webui_conversation_inputs(materialized_message_id)
            WHERE materialized_message_id IS NOT NULL AND regeneration_request_json IS NULL;
        ALTER TABLE webui_agent_turns
            ADD COLUMN manual_regeneration_request_json TEXT
            CHECK(manual_regeneration_request_json IS NULL OR (
                json_valid(manual_regeneration_request_json)
                AND json_type(manual_regeneration_request_json) = 'object'
            ));
        ALTER TABLE webui_agent_turns
            ADD COLUMN manual_regeneration_accepted_revision INTEGER
            CHECK(manual_regeneration_accepted_revision IS NULL OR manual_regeneration_accepted_revision >= 1000000000000)
            CHECK((manual_regeneration_request_json IS NULL) = (manual_regeneration_accepted_revision IS NULL));
        CREATE UNIQUE INDEX idx_agent_turns_manual_regeneration_identity
            ON webui_agent_turns(
                conv_id,
                user_id,
                json_extract(manual_regeneration_request_json, '$.client_id'),
                json_extract(manual_regeneration_request_json, '$.client_request_id')
            ) WHERE manual_regeneration_request_json IS NOT NULL;
        CREATE TABLE hardware_gpu_soaibench_publications (
            run_id TEXT PRIMARY KEY
                CHECK(length(run_id) = 32 AND run_id NOT GLOB '*[^0-9a-f]*'),
            created_by_user_id INTEGER NOT NULL CHECK(created_by_user_id > 0),
            installation_id TEXT NOT NULL
                CHECK(length(installation_id) = 36 AND installation_id = lower(installation_id)),
            canonical_submission_json TEXT NOT NULL
                CHECK(length(CAST(canonical_submission_json AS BLOB)) BETWEEN 2 AND 262144)
                CHECK(json_valid(canonical_submission_json) AND json_type(canonical_submission_json) = 'object'),
            state TEXT NOT NULL CHECK(state IN ('prepared', 'published')),
            prepared_at_ms INTEGER NOT NULL CHECK(prepared_at_ms >= 0),
            published_at_ms INTEGER CHECK(published_at_ms IS NULL OR published_at_ms >= prepared_at_ms),
            receipt_json TEXT
                CHECK(receipt_json IS NULL OR length(CAST(receipt_json AS BLOB)) BETWEEN 2 AND 16384)
                CHECK(receipt_json IS NULL OR (json_valid(receipt_json) AND json_type(receipt_json) = 'object')),
            CHECK(
                (state = 'prepared' AND published_at_ms IS NULL AND receipt_json IS NULL)
                OR
                (state = 'published' AND published_at_ms IS NOT NULL AND receipt_json IS NOT NULL)
            )
        ) STRICT;
        """,
    )
