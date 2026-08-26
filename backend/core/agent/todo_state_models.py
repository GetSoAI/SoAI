"""SoAI - Shared agent todo-state models [backend/core/agent/todo_state_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict

__all__ = ("AgentTurnTodoState",)


@dataclass(slots=True)
class AgentTurnTodoState:
    todo: list[JSONDict]
    todo_explanation: str | None
    todo_revision: int
    todo_updated_at_ms: int | None
