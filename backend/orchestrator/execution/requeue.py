"""SoAI - Executor internal requeue signal [backend/orchestrator/execution/requeue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("RequeueTask",)


class RequeueTask(StateError):
    def __init__(self) -> None:
        super().__init__(
            message="Task requires requeue due to plugin state change",
            operation="orchestrator.execute_inference",
        )
