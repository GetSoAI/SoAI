"""SoAI - Shared agent state exception types [backend/core/agent/state_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "AgentStateError",
    "AgentStateManualEditConflictError",
    "AgentStateManualEditUnavailableError",
    "AgentStateRevisionConflictError",
)


class AgentStateError(RuntimeError):
    __slots__ = ()


class AgentStateRevisionConflictError(AgentStateError):
    __slots__ = ()


class AgentStateManualEditConflictError(AgentStateError):
    __slots__ = ()


class AgentStateManualEditUnavailableError(AgentStateError):
    __slots__ = ()
