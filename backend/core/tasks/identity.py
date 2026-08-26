"""SoAI - Task identity payload helpers [backend/core/tasks/identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.protocols import TaskIdentityProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_task_identity_payload",)


def build_task_identity_payload(task: TaskIdentityProtocol) -> JSONDict:
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status.value,
        "user_id": task.user_id,
        "owner_id": task.owner_id,
        "owner_type": task.owner_type,
    }
