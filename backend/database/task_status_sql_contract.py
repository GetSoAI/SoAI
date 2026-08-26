"""SoAI - Task status SQL CHECK constraint validation [backend/database/task_status_sql_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.tasks.enums import (
    TASK_STATUS_SQL_VALUES,
    TaskStatus,
)

__all__ = ("validate_task_status_sql_contract",)


def validate_task_status_sql_contract() -> None:
    enum_task_statuses_ordered = tuple(status.value for status in TaskStatus)
    if enum_task_statuses_ordered != TASK_STATUS_SQL_VALUES:
        raise StateError(
            "TaskStatus enum SQL values mismatch (enum definition does not match TASK_STATUS_SQL_VALUES).",
        )
