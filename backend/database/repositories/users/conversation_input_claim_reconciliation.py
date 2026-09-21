"""SoAI - Conversation input abandoned claim reconciliation [backend/database/repositories/users/conversation_input_claim_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.model_settings.normalization import resolve_execution_model_sequence
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from core.types.json import is_json_dict
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.repositories.tasks.conversation_interaction_wake import (
    sync_reconcile_terminal_interaction_input_wakes,
)
from database.repositories.users.conversation_input_assistant_recovery import (
    sync_finalize_abandoned_conversation_input_assistants,
)
from database.repositories.users.conversation_input_cancellation_recovery import (
    sync_recover_cancelled_conversation_input,
)
from database.repositories.users.conversation_input_row_mapping import (
    format_conversation_input_row,
)
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
)
from database.repositories.users.conversation_stream_cancellation_state import (
    sync_has_chat_stream_cancellation_for_input,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_reconcile_abandoned_conversation_input_claims",)


def _terminal_state_for_finish_reason(finish_reason: str | None) -> tuple[str, str]:
    if finish_reason == "cancelled":
        return ("cancelled", "cancelled")
    if finish_reason == "error":
        return ("failed", "interrupted_after_finalization")
    return ("completed", "recovered_completed")


def _recover_running_input(
    sqlite_conn: sqlite3.Connection,
    *,
    input_id: str,
    conv_id: str,
    user_id: int,
    request_id: str,
    expected_variant_count: int,
    recovered_at_ms: int,
) -> None:
    assistants, source_message_id = sync_finalize_abandoned_conversation_input_assistants(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        request_id=request_id,
        finish_reason="error",
        terminal_reason="Chat stream execution was interrupted during recovery.",
    )
    if not assistants:
        sqlite_conn.execute(
            """
            UPDATE webui_conversation_inputs
            SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
                claimed_at_ms = NULL, running_at_ms = NULL, updated_at_ms = ?
            WHERE input_id = ? AND state = 'running'
            """,
            (recovered_at_ms, input_id),
        )
        return
    request_ids = {assistant.request_id for assistant in assistants}
    recovery_is_uncertain = (
        len(request_ids) != len(assistants)
        or len(assistants) > expected_variant_count
        or any(assistant.finalized_at_ms is None for assistant in assistants)
    )
    if recovery_is_uncertain:
        terminal_state, terminal_code = ("effect_unknown", "interrupted_effect_unknown")
    else:
        failed_assistant = next(
            (
                assistant
                for assistant in assistants
                if assistant.finish_reason in {"cancelled", "error"}
            ),
            None,
        )
        if failed_assistant is not None:
            terminal_state, terminal_code = _terminal_state_for_finish_reason(
                failed_assistant.finish_reason,
            )
            source_message_id = failed_assistant.message_id
        elif len(assistants) == expected_variant_count:
            terminal_state, terminal_code = ("completed", "recovered_completed")
            final_assistant = next(
                (
                    assistant
                    for assistant in assistants
                    if assistant.model_variant_index == expected_variant_count - 1
                ),
                None,
            )
            if final_assistant is None:
                raise StateError("Recovered final assistant variant is unavailable.")
            source_message_id = final_assistant.message_id
        else:
            sqlite_conn.execute(
                """
                UPDATE webui_conversation_inputs
                SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
                    claimed_at_ms = NULL, running_at_ms = NULL, updated_at_ms = ?
                WHERE input_id = ? AND state = 'running'
                """,
                (recovered_at_ms, input_id),
            )
            return
    updated = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = ?, terminal_code = ?, terminal_args_json = ?,
            terminal_at_ms = ?, updated_at_ms = ?
        WHERE input_id = ? AND state = 'running'
        """,
        (
            terminal_state,
            terminal_code,
            serialize_json_compact_stable({}),
            recovered_at_ms,
            recovered_at_ms,
            input_id,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Recoverable conversation input changed during reconciliation.")
    sync_ensure_conversation_input_terminal_event(
        sqlite_conn,
        input_id=input_id,
        user_id=user_id,
        conv_id=conv_id,
        source_message_id=source_message_id,
        terminal_state=terminal_state,
        terminal_code=terminal_code,
        created_at_ms=recovered_at_ms,
    )


def sync_reconcile_abandoned_conversation_input_claims(
    sqlite_conn: sqlite3.Connection,
) -> list[JSONDict]:
    sync_reconcile_terminal_interaction_input_wakes(
        sqlite_conn,
        resolved_at_ms=epoch_ms(),
    )
    rows = sync_fetch_all_as_dicts(
        sqlite_conn.execute(
            """
            SELECT candidate.*,
                   COALESCE(candidate.model_settings_json, target.model_settings_json)
                       AS execution_model_settings_json
            FROM webui_conversation_inputs AS candidate
            LEFT JOIN webui_conversation_inputs AS target
              ON target.input_id = candidate.target_input_id
            WHERE candidate.state IN ('materializing', 'running')
            ORDER BY candidate.accepted_at_ms ASC, candidate.id ASC
            """,
        ),
    )
    recovered_at_ms = epoch_ms()
    for row in rows:
        input_id = row.get("input_id")
        state = row.get("state")
        conv_id = row.get("conv_id")
        user_id = row.get("user_id")
        stored_request_id = row.get("request_id")
        if (
            not isinstance(input_id, str)
            or not isinstance(conv_id, str)
            or not isinstance(user_id, int)
        ):
            raise StateError("Recoverable conversation input identity is invalid.")
        request_id = (
            stored_request_id
            if isinstance(stored_request_id, str) and stored_request_id
            else f"chat_{input_id}"
        )
        if sync_has_chat_stream_cancellation_for_input(
            sqlite_conn,
            user_id,
            conv_id,
            request_id,
        ):
            sync_recover_cancelled_conversation_input(
                sqlite_conn,
                input_id=input_id,
                conv_id=conv_id,
                user_id=user_id,
                request_id=request_id,
                recovered_at_ms=recovered_at_ms,
            )
            continue
        if state == "materializing":
            sqlite_conn.execute(
                """
                UPDATE webui_conversation_inputs
                SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
                    claimed_at_ms = NULL, updated_at_ms = ?
                WHERE input_id = ? AND state = 'materializing'
                """,
                (recovered_at_ms, input_id),
            )
            continue
        if not isinstance(stored_request_id, str) or not stored_request_id:
            raise StateError("Recoverable running input request id is invalid.")
        settings_json = row.get("execution_model_settings_json")
        if not isinstance(settings_json, str) or not settings_json:
            raise StateError("Recoverable running input settings are unavailable.")
        model_settings = safe_json_deserialize(settings_json)
        if not is_json_dict(model_settings):
            raise StateError("Recoverable running input settings are invalid.")
        _recover_running_input(
            sqlite_conn,
            input_id=input_id,
            conv_id=conv_id,
            user_id=user_id,
            request_id=request_id,
            expected_variant_count=len(resolve_execution_model_sequence(model_settings)),
            recovered_at_ms=recovered_at_ms,
        )
    recovered_rows: list[JSONDict] = []
    for row in rows:
        input_id = row.get("input_id")
        updated = sync_fetch_one_as_dict(
            sqlite_conn.execute(
                "SELECT * FROM webui_conversation_inputs WHERE input_id = ? LIMIT 1",
                (input_id,),
            ),
        )
        if updated is None:
            raise StateError("Recovered conversation input is unavailable.")
        formatted = format_conversation_input_row(updated)
        if formatted is None:
            raise StateError("Recovered conversation input is unavailable.")
        recovered_rows.append(formatted)
    return recovered_rows
