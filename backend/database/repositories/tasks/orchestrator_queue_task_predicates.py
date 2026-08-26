"""SoAI - Durable orchestrator queue SQL task predicates [backend/database/repositories/tasks/orchestrator_queue_task_predicates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.status_policy import active_task_status_placeholders

__all__ = ("active_task_exists_clause",)


def active_task_exists_clause() -> str:
    return f"""
                   AND EXISTS (
                       SELECT 1
                         FROM unified_tasks AS ut
                        WHERE ut.task_id = orchestrator_queue_items.task_id
                          AND ut.status IN ({active_task_status_placeholders()})
                   )
    """
