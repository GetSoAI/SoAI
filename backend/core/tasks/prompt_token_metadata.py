"""SoAI - Task prompt-token metadata resolution [backend/core/tasks/prompt_token_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.quotas.token_reservation_payloads import read_token_quota_prompt_tokens
from core.tasks.task import Task

__all__ = ("resolve_task_prompt_tokens",)


def resolve_task_prompt_tokens(task: Task) -> int | None:
    metadata = task.metadata
    if not isinstance(metadata, Mapping):
        return None
    return read_token_quota_prompt_tokens(metadata)
