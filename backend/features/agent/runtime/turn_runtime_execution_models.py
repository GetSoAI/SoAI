"""SoAI - Agent turn runtime execution models [backend/features/agent/runtime/turn_runtime_execution_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.openai.usage.models import CanonicalUsage
    from features.agent.runtime.persisted_terminal_turn_replay import (
        PersistedTerminalTurnReplay,
    )
    from features.agent.runtime.turn_engine import AgentTurnResult

__all__ = ("TurnRuntimeExecution",)


@dataclass(frozen=True, slots=True)
class TurnRuntimeExecution:
    result: AgentTurnResult
    usage_aggregate: CanonicalUsage | None
    stream_id: str | None
    persisted_terminal_turn_replay: PersistedTerminalTurnReplay | None = None
