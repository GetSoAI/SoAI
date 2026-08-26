"""SoAI - API runtime user typing helpers [backend/features/api/runtime/user_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NotRequired

from core.tasks.api_queries import TaskVisibilityUserPayload

__all__ = ("CurrentUser",)


class CurrentUser(TaskVisibilityUserPayload):
    username: NotRequired[str]
    workspace_path: NotRequired[str]
    default_workspace_path: NotRequired[str]
    identity_revision: NotRequired[int]
