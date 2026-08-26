"""SoAI - Database schema: assistant usage contract triggers [backend/database/schema_scripts/assistant_usage_triggers_sql.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

ASSISTANT_USAGE_TRIGGER_SQL = """
        CREATE TRIGGER IF NOT EXISTS trg_webui_messages_assistant_usage_contract_insert
        BEFORE INSERT ON webui_messages
        FOR EACH ROW
        WHEN NEW.role = 'assistant'
        BEGIN
            SELECT CASE
                WHEN ((NEW.prompt_tokens IS NULL) != (NEW.completion_tokens IS NULL))
                    OR ((NEW.prompt_tokens IS NULL) != (NEW.total_tokens IS NULL))
                THEN RAISE(ABORT, 'assistant token columns must be all-null or all-present')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.request_id IS NULL OR length(trim(NEW.request_id)) = 0)
                THEN RAISE(ABORT, 'assistant request_id is required when tokens are persisted')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.usage_source IS NULL OR length(trim(NEW.usage_source)) = 0)
                THEN RAISE(ABORT, 'assistant usage_source is required when tokens are persisted')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.prompt_tokens < 0 OR NEW.completion_tokens < 0 OR NEW.total_tokens < 0)
                THEN RAISE(ABORT, 'assistant token columns must be non-negative')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND NEW.total_tokens != (NEW.prompt_tokens + NEW.completion_tokens)
                THEN RAISE(ABORT, 'assistant total_tokens must equal prompt_tokens + completion_tokens')
            END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_messages_assistant_usage_contract_update
        BEFORE UPDATE ON webui_messages
        FOR EACH ROW
        WHEN NEW.role = 'assistant'
        BEGIN
            SELECT CASE
                WHEN ((NEW.prompt_tokens IS NULL) != (NEW.completion_tokens IS NULL))
                    OR ((NEW.prompt_tokens IS NULL) != (NEW.total_tokens IS NULL))
                THEN RAISE(ABORT, 'assistant token columns must be all-null or all-present')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.request_id IS NULL OR length(trim(NEW.request_id)) = 0)
                THEN RAISE(ABORT, 'assistant request_id is required when tokens are persisted')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.usage_source IS NULL OR length(trim(NEW.usage_source)) = 0)
                THEN RAISE(ABORT, 'assistant usage_source is required when tokens are persisted')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND (NEW.prompt_tokens < 0 OR NEW.completion_tokens < 0 OR NEW.total_tokens < 0)
                THEN RAISE(ABORT, 'assistant token columns must be non-negative')
            END;
            SELECT CASE
                WHEN NEW.prompt_tokens IS NOT NULL
                    AND NEW.total_tokens != (NEW.prompt_tokens + NEW.completion_tokens)
                THEN RAISE(ABORT, 'assistant total_tokens must equal prompt_tokens + completion_tokens')
            END;
        END;
"""
