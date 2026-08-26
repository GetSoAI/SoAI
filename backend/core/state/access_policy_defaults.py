"""SoAI - Core ACL immutable/default role action sets [backend/core/state/access_policy_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.access import AccessAction, AccessState

__all__ = ()

IMMUTABLE_POLICY_STATES: frozenset[AccessState] = frozenset(
    {AccessState.UNINITIALIZED, AccessState.ANONYMOUS},
)
ADMIN_REQUIRED_ACTIONS: frozenset[AccessAction] = frozenset(
    {AccessAction.ACL_ADMIN, AccessAction.LICENSING_ADMIN, AccessAction.RECOVERY_ADMIN}
)
STANDARD_GRANTABLE_ACTIONS: frozenset[AccessAction] = frozenset(
    {
        AccessAction.AUTH_COOKIE,
        AccessAction.NOTIFICATIONS,
        AccessAction.SYSTEM_STATUS_READ,
        AccessAction.HARDWARE_READ,
        AccessAction.MODEL_READ,
        AccessAction.PLUGIN_READ,
        AccessAction.MODEL_ROUTING_READ,
        AccessAction.SEARCH_READ,
        AccessAction.OPENAI_API,
        AccessAction.TASK_MANAGEMENT,
        AccessAction.FILE_EXPLORER_READ,
        AccessAction.FILE_EXPLORER_HASH,
        AccessAction.WEB_SEARCH,
        AccessAction.RAG_USE,
        AccessAction.MCP_USE,
        AccessAction.TERMINAL_USE,
    },
)
STANDARD_DEFAULT_ACTIONS: frozenset[AccessAction] = frozenset(
    {
        AccessAction.AUTH_COOKIE,
        AccessAction.NOTIFICATIONS,
        AccessAction.MODEL_READ,
        AccessAction.PLUGIN_READ,
        AccessAction.SEARCH_READ,
        AccessAction.OPENAI_API,
        AccessAction.TASK_MANAGEMENT,
        AccessAction.FILE_EXPLORER_READ,
        AccessAction.FILE_EXPLORER_HASH,
        AccessAction.WEB_SEARCH,
        AccessAction.RAG_USE,
        AccessAction.MCP_USE,
    }
)
