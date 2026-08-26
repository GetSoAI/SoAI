"""SoAI - Atomic unified-task finalization persistence [backend/database/repositories/tasks/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.database.task_requests import UnifiedTaskFinalizationWriteResult
from core.tasks.status_policy import ACTIVE_TASK_STATUS_VALUES, active_task_status_placeholders
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import require_positive_int_strict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.tasks.conversation_interaction_finalization import (
    sync_apply_conversation_interaction_mutation,
)
from database.repositories.tasks.conversation_interaction_wake import (
    sync_wake_conversation_input_for_terminal_interaction,
)
from database.repositories.tasks.mutation_finalization import sync_finalize_mutation_for_task
from database.repositories.tasks.orchestrator_queue_phases import (
    sync_finalize_orchestrator_queue_item,
)

if TYPE_CHECKING:
    from core.tasks.interaction_mutations import ConversationInteractionMutation
    from database.core.sqlite_values import SQLiteValue

__all__ = ("sync_finalize_unified_task",)


def sync_finalize_unified_task(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    task_id: str,
    status: str,
    result: str | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
    mutation_fencing_token: int | None = None,
    interaction_mutation: ConversationInteractionMutation | None = None,
) -> UnifiedTaskFinalizationWriteResult:
    if mutation_fencing_token is not None:
        require_positive_int_strict(
            mutation_fencing_token,
            error_message="Task finalization requires a positive mutation fencing token.",
        )
    now = epoch_ms()
    mutation_claim_predicate = ""
    mutation_claim_parameters: tuple[SQLiteValue, ...] = ()
    if mutation_fencing_token is not None:
        mutation_claim_predicate = """AND EXISTS (
                   SELECT 1 FROM mutation_admissions
                   WHERE accepted_task_id = ?
                     AND lifecycle_status = 'running'
                     AND fencing_token = ?
                     AND claim_owner IS NOT NULL
        )"""
        mutation_claim_parameters = (task_id, mutation_fencing_token)
    else:
        mutation_claim_predicate = """AND NOT EXISTS (
                   SELECT 1 FROM mutation_admissions
                   WHERE accepted_task_id = ?
                     AND lifecycle_status = 'running'
               )"""
        mutation_claim_parameters = (task_id,)
    updated = (
        conn.execute(
            f"""
            UPDATE unified_tasks
               SET status = ?,
                   result = ?,
                   error_code = ?,
                   error_type = ?,
                   error_message = ?,
                   status_message = ?,
                   updated_at_ms = ?,
                   completed_at_ms = ?,
                   orchestration_state = NULL,
                   progress_current = CASE
                       WHEN progress_total IS NOT NULL THEN progress_total
                       ELSE progress_current
                   END
             WHERE task_id = ?
               AND status IN ({active_task_status_placeholders()})
               {mutation_claim_predicate}
            """,
            (
                status,
                result,
                error_code,
                error_type,
                error_message,
                status_message,
                now,
                now,
                task_id,
                *ACTIVE_TASK_STATUS_VALUES,
                *mutation_claim_parameters,
            ),
        ).rowcount
        > 0
    )
    if updated:
        if interaction_mutation is not None:
            sync_apply_conversation_interaction_mutation(
                conn,
                fernets,
                task_id=task_id,
                mutation=interaction_mutation,
                created_at_ms=now,
            )
        sync_wake_conversation_input_for_terminal_interaction(
            conn,
            task_id=task_id,
            task_status=status,
            resolved_at_ms=now,
        )
        sync_finalize_orchestrator_queue_item(conn, task_id, status)
        sync_finalize_mutation_for_task(
            conn,
            task_id,
            status,
            result,
            completed_at_ms=now,
        )
        return UnifiedTaskFinalizationWriteResult(
            updated=True,
            current_status=status,
            completed_at_ms=now,
        )
    current = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT status, completed_at_ms FROM unified_tasks WHERE task_id = ?",
            (task_id,),
        ),
    )
    current_status_value = current.get("status") if current is not None else None
    completed_at_value = current.get("completed_at_ms") if current is not None else None
    return UnifiedTaskFinalizationWriteResult(
        updated=False,
        current_status=(current_status_value if isinstance(current_status_value, str) else None),
        completed_at_ms=(completed_at_value if isinstance(completed_at_value, int) else None),
    )
