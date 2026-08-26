"""SoAI - Manual compaction execution identity [backend/features/api/routes/webui/conversation_agent_compaction/execution_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ManualCompactionExecutionIdentity",)


@dataclass(frozen=True, slots=True)
class ManualCompactionExecutionIdentity:
    conv_id: str
    user_id: int
    turn_id: str
    iteration_index: int
    tool_call_id: str
    tool_started_at_ms: int
