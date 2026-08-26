"""SoAI - Restricted repair-plane access actions [backend/core/state/repair_plane.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.access import AccessAction

REPAIR_PLANE_ACTIONS: frozenset[AccessAction] = frozenset(
    {
        AccessAction.WIZARD_BOOTSTRAP,
        AccessAction.AUTH_COOKIE,
        AccessAction.NOTIFICATIONS,
        AccessAction.REQUEST_CANCELLATION_ADMIN,
        AccessAction.SYSTEM_POWER,
        AccessAction.MODEL_READ,
        AccessAction.LOG_ACCESS,
        AccessAction.SYSTEM_STATUS_READ,
        AccessAction.PLUGIN_READ,
        AccessAction.HARDWARE_READ,
        AccessAction.BACKUP_ADMIN,
        AccessAction.FILE_EXPLORER_READ,
        AccessAction.FILE_EXPLORER_HASH,
        AccessAction.LICENSING_ADMIN,
        AccessAction.RECOVERY_ADMIN,
    }
)


def restrict_to_repair_plane(actions: frozenset[AccessAction]) -> frozenset[AccessAction]:
    return actions.intersection(REPAIR_PLANE_ACTIONS)


__all__ = ("REPAIR_PLANE_ACTIONS", "restrict_to_repair_plane")
