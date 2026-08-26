"""SoAI - Manual compaction internal protocols [backend/features/api/routes/webui/conversation_agent_compaction/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("ManualCompactionStartStateProtocol",)


class ManualCompactionStartStateProtocol(Protocol):
    @property
    def conv_id(self) -> str: ...

    @property
    def tool_call_id(self) -> str: ...

    @property
    def message_index(self) -> int: ...

    @property
    def turn_id(self) -> str: ...

    @property
    def iteration_index(self) -> int: ...

    @property
    def started_at_ms(self) -> int: ...
