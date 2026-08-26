"""SoAI - Agent turn write conflict classification [backend/core/agent/turn_write_conflicts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "TURN_WRITE_ALREADY_FINALIZED_MESSAGE",
    "TURN_WRITE_STALE_ITERATION_MESSAGE",
    "TURN_WRITE_STALE_SEQUENCE_MESSAGE",
    "TURN_WRITE_STALE_UPDATE_MESSAGE",
    "AgentTurnAlreadyFinalizedDuringWriteError",
    "AgentTurnFinalizedWriteConflictError",
    "AgentTurnStaleProgressError",
)

TURN_WRITE_ALREADY_FINALIZED_MESSAGE = "Agent turn already finalized."
TURN_WRITE_STALE_UPDATE_MESSAGE = "Agent turn update is stale."
TURN_WRITE_STALE_ITERATION_MESSAGE = "Agent turn iteration_index is stale."
TURN_WRITE_STALE_SEQUENCE_MESSAGE = "Agent turn sequence is stale."


class AgentTurnAlreadyFinalizedDuringWriteError(RuntimeError):
    __slots__ = ()


class AgentTurnFinalizedWriteConflictError(ValidationError): ...


class AgentTurnStaleProgressError(ValidationError): ...
