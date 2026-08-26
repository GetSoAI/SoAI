"""SoAI - ACL action licensing classification [backend/core/licensing/access_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.licensing.types import LicensingStatus
from core.state.access import AccessAction
from core.state.repair_plane import REPAIR_PLANE_ACTIONS, restrict_to_repair_plane

ORDINARY_ACTIONS: frozenset[AccessAction] = frozenset(
    {
        AccessAction.USER_ADMIN,
        AccessAction.CONFIG_PATCH,
        AccessAction.TERMINAL_USE,
        AccessAction.HW_GPU_TUNING,
        AccessAction.PLUGIN_ADMIN,
        AccessAction.FACTORY_RESET,
        AccessAction.METRICS_RESET,
        AccessAction.MODEL_ADMIN,
        AccessAction.MODEL_ROUTING_READ,
        AccessAction.MODEL_ROUTING_ADMIN,
        AccessAction.SOFTWARE_UPDATE,
        AccessAction.ACL_ADMIN,
        AccessAction.SEARCH_READ,
        AccessAction.OPENAI_API,
        AccessAction.WEBUI_APPEARANCE_ADMIN,
        AccessAction.OPENAI_API_ADMIN,
        AccessAction.MCP_ADMIN,
        AccessAction.TASK_MANAGEMENT,
        AccessAction.HW_PROCESS_VIEW,
        AccessAction.FILE_EXPLORER_WRITE,
        AccessAction.FILE_EXPLORER_ADMIN,
        AccessAction.HOST_MANAGEMENT_ADMIN,
        AccessAction.WEB_SEARCH,
        AccessAction.RAG_USE,
        AccessAction.MCP_USE,
    }
)


def validate_action_licensing_classification() -> None:
    if REPAIR_PLANE_ACTIONS & ORDINARY_ACTIONS:
        raise StateError("Licensing action classes overlap.")
    if REPAIR_PLANE_ACTIONS | ORDINARY_ACTIONS != frozenset(AccessAction):
        raise StateError("Licensing action classification is incomplete.")


def apply_licensing_action_policy(
    actions: frozenset[AccessAction],
    status: LicensingStatus,
) -> frozenset[AccessAction]:
    if status.requires_repair_plane:
        return restrict_to_repair_plane(actions)
    return actions


__all__ = (
    "ORDINARY_ACTIONS",
    "REPAIR_PLANE_ACTIONS",
    "apply_licensing_action_policy",
    "validate_action_licensing_classification",
)
