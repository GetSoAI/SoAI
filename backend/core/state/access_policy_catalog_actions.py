"""SoAI - Core ACL action catalog entries [backend/core/state/access_policy_catalog_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.state.access import AccessAction, AccessState

__all__ = (
    "AccessActionCatalogEntry",
    "build_access_action_catalog",
)


@dataclass(frozen=True, slots=True)
class AccessActionCatalogEntry:
    action: AccessAction
    roles: frozenset[AccessState]
    locked_roles: frozenset[AccessState] = frozenset()
    order: int = 0


def build_access_action_catalog() -> tuple[AccessActionCatalogEntry, ...]:
    return (
        AccessActionCatalogEntry(
            action=AccessAction.WIZARD_BOOTSTRAP,
            roles=frozenset({AccessState.UNINITIALIZED}),
            locked_roles=frozenset({AccessState.UNINITIALIZED}),
            order=10,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.AUTH_COOKIE,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=20,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.NOTIFICATIONS,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=25,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.USER_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=30,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.CONFIG_PATCH,
            roles=frozenset({AccessState.ADMIN}),
            order=40,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.TERMINAL_USE,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=50,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.HW_GPU_TUNING,
            roles=frozenset({AccessState.ADMIN}),
            order=60,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.PLUGIN_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=70,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.FACTORY_RESET,
            roles=frozenset({AccessState.ADMIN}),
            order=80,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.METRICS_RESET,
            roles=frozenset({AccessState.ADMIN}),
            order=90,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.REQUEST_CANCELLATION_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=100,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.SYSTEM_POWER,
            roles=frozenset({AccessState.ADMIN}),
            order=110,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MODEL_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=120,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MODEL_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=130,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MODEL_ROUTING_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=140,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MODEL_ROUTING_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=150,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.SOFTWARE_UPDATE,
            roles=frozenset({AccessState.ADMIN}),
            order=160,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.LOG_ACCESS,
            roles=frozenset({AccessState.ADMIN}),
            order=170,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.ACL_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            locked_roles=frozenset({AccessState.ADMIN}),
            order=180,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.SYSTEM_STATUS_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=190,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.PLUGIN_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=200,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.HARDWARE_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=210,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.SEARCH_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=220,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.OPENAI_API,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=230,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.WEBUI_APPEARANCE_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=240,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.OPENAI_API_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=250,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MCP_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=260,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.TASK_MANAGEMENT,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=270,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.HW_PROCESS_VIEW,
            roles=frozenset({AccessState.ADMIN}),
            order=280,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.BACKUP_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=290,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.FILE_EXPLORER_READ,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=300,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.FILE_EXPLORER_WRITE,
            roles=frozenset({AccessState.ADMIN}),
            order=310,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.FILE_EXPLORER_HASH,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=320,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.FILE_EXPLORER_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=330,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.HOST_MANAGEMENT_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            order=340,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.WEB_SEARCH,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=350,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.RAG_USE,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=360,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.MCP_USE,
            roles=frozenset({AccessState.ADMIN, AccessState.STANDARD}),
            order=370,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.LICENSING_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            locked_roles=frozenset({AccessState.ADMIN}),
            order=380,
        ),
        AccessActionCatalogEntry(
            action=AccessAction.RECOVERY_ADMIN,
            roles=frozenset({AccessState.ADMIN}),
            locked_roles=frozenset({AccessState.ADMIN}),
            order=390,
        ),
    )
