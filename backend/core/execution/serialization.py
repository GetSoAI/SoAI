"""SoAI - Shared execution snapshot serialization helpers [backend/core/execution/serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.execution.protocols import OwnedExecutionCore

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("serialize_owned_execution_core",)


def serialize_owned_execution_core(snapshot: OwnedExecutionCore) -> JSONDict:
    return {
        "execution_type": snapshot.execution_type,
        "owner_task_id": snapshot.owner_task_id,
        "status": snapshot.status,
        "status_message": snapshot.status_message,
        "started_at_ms": snapshot.started_at_ms,
        "updated_at_ms": snapshot.updated_at_ms,
        "finished_at_ms": snapshot.finished_at_ms,
        "requested_model": snapshot.requested_model,
        "token_usage": snapshot.token_usage,
    }
