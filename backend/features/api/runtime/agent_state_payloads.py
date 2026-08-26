"""SoAI - Agent WebUI payload shaping [backend/features/api/runtime/agent_state_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.subagent_serialization import serialize_subagent_snapshots
from core.agent.turn_serialization import serialize_agent_turn_snapshot
from core.execution.protocols import AgentTurnSnapshot, SubagentSnapshot

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_agent_checkpoint_payload",)


def build_agent_checkpoint_payload(
    *,
    snapshot: AgentTurnSnapshot,
    subagent_snapshots: list[SubagentSnapshot],
) -> JSONDict:
    payload = serialize_agent_turn_snapshot(snapshot)
    payload["subagents"] = serialize_subagent_snapshots(subagent_snapshots)
    return payload
