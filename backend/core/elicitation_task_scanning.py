"""SoAI - Pending conversation elicitation task scanning [backend/core/elicitation_task_scanning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

from core.elicitation_ask_user import ASK_USER_INTERACTION_TYPE
from core.elicitation_vault_secret_request import CREDENTIAL_REQUEST_INTERACTION_TYPE
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION
from core.timing.epoch import epoch_ms
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = (
    "iter_pending_conversation_elicitation_tasks",
    "resolve_pending_conversation_elicitation_interaction_type",
)

_PENDING_INTERACTION_PRIORITY: tuple[str, ...] = (
    TOOL_APPROVAL_INTERACTION_TYPE,
    CREDENTIAL_REQUEST_INTERACTION_TYPE,
    ASK_USER_INTERACTION_TYPE,
)


def iter_pending_conversation_elicitation_tasks(
    tasks: Iterable[Task],
    *,
    conv_id: str,
) -> Iterator[Task]:
    normalized_conv_id = conv_id.strip()
    if not normalized_conv_id:
        return
    now_ms = epoch_ms()
    for task in tasks:
        if task.owner_type != "conversation" or task.owner_id != normalized_conv_id:
            continue
        if task.task_type != TASK_TYPE_MCP_ELICITATION:
            continue
        if task.status != TaskStatus.INPUT_REQUIRED:
            continue
        if task.ttl_expires_at_ms is not None and task.ttl_expires_at_ms <= now_ms:
            continue
        yield task


def resolve_pending_conversation_elicitation_interaction_type(
    tasks: Iterable[Task],
    *,
    conv_id: str,
) -> str | None:
    has_pending: dict[str, bool] = dict.fromkeys(_PENDING_INTERACTION_PRIORITY, False)
    for task in iter_pending_conversation_elicitation_tasks(tasks, conv_id=conv_id):
        interaction_value = task.metadata.get("interaction_type")
        interaction_key = interaction_value.strip() if isinstance(interaction_value, str) else ""
        if interaction_key in has_pending:
            has_pending[interaction_key] = True
    for interaction_type in _PENDING_INTERACTION_PRIORITY:
        if has_pending[interaction_type]:
            return interaction_type
    return None
