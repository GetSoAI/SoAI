"""SoAI - Default config schema: task manager [backend/core/config/default_schema/task_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_task_manager_defaults",)


def build_task_manager_defaults() -> ConfigDict:
    return {
        "TASKS": {
            "CANCELLATION_HISTORY_LIMIT": 2048,
            "CANCELLATION_LISTENER_QUEUE_SIZE": 1,
            "DEFAULT_TTL_SECONDS": 3600,
            "CLEANUP_INTERVAL_SECONDS": 300,
            "MEMORY_CACHE_MAX_SIZE": 10000,
            "TERMINAL_CACHE_GRACE_SECONDS": 60,
            "STUCK_TASK_TIMEOUT_SECONDS": 3600,
            "MAX_CONCURRENT_PER_OWNER": 100,
            "MAX_CONCURRENT_PER_HTTP_REQUEST": 100,
            "MAX_CONCURRENT_PER_SYSTEM": 100,
            "MAX_CONCURRENT_PER_CONVERSATION": 100,
            "TASK_LIST_MAX_LIMIT": 1000,
            "TASK_LIST_MAX_OFFSET": 10000,
            "ACTIVE_TASKS_LIMIT": 1000,
        },
    }
