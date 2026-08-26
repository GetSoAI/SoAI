"""SoAI - Task registry query dependency contracts [backend/tasks/registry/query_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.tasks.protocols_query import DatabaseTaskQueriesProtocol
from core.tasks.type_catalog import TaskTypeCatalog

__all__ = ("TaskRegistryQueriesDependencies",)


@dataclass(frozen=True, slots=True)
class TaskRegistryQueriesDependencies:
    database_tasks: DatabaseTasksProtocol
    database_task_queries: DatabaseTaskQueriesProtocol
    task_catalog: TaskTypeCatalog

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskRegistryQueriesDependencies",
            database_task_queries=self.database_task_queries,
            database_tasks=self.database_tasks,
            task_catalog=self.task_catalog,
        )
