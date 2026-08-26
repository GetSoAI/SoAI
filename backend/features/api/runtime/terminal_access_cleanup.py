"""SoAI - API terminal session cleanup after access changes [backend/features/api/runtime/terminal_access_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.state.access import AccessAction, AccessState
from core.types.json import JSONValue
from core.users.user_id import coerce_user_id

if TYPE_CHECKING:
    from core.state.access import AccessPolicyMatrix
    from features.api.runtime.context import ApiContext

__all__ = (
    "close_terminal_sessions_for_user",
    "close_terminal_sessions_for_user_state_change",
    "close_terminal_sessions_for_users_losing_access",
    "user_record_access_state",
)


def user_record_access_state(user: Mapping[str, JSONValue]) -> AccessState:
    if user.get("is_admin") is True:
        return AccessState.ADMIN
    return AccessState.STANDARD


async def close_terminal_sessions_for_user(api_context: ApiContext, *, user_id: int) -> int:
    if user_id <= 0:
        return 0
    closed_count = await api_context.dependencies.terminal.close_pty_sessions_for_user(user_id)
    closed_count += await api_context.dependencies.mcp_server.cancel_user_shell_sessions(
        user_id=user_id,
    )
    return closed_count


async def close_terminal_sessions_for_users_losing_access(
    api_context: ApiContext,
    *,
    previous_policy: AccessPolicyMatrix,
    next_policy: AccessPolicyMatrix,
) -> int:
    users = await api_context.dependencies.webui_manager.database_users.list_human_users()
    closed_count = 0
    for user in users:
        state = user_record_access_state(user)
        had_access = AccessAction.TERMINAL_USE in previous_policy.get(state, frozenset())
        has_access = AccessAction.TERMINAL_USE in next_policy.get(state, frozenset())
        if had_access and not has_access:
            closed_count += await close_terminal_sessions_for_user(
                api_context,
                user_id=coerce_user_id(user.get("id")),
            )
    return closed_count


async def close_terminal_sessions_for_user_state_change(
    api_context: ApiContext,
    *,
    user_id: int,
    previous_state: AccessState,
    next_state: AccessState,
    policy: AccessPolicyMatrix,
) -> int:
    had_access = AccessAction.TERMINAL_USE in policy.get(previous_state, frozenset())
    has_access = AccessAction.TERMINAL_USE in policy.get(next_state, frozenset())
    if had_access and not has_access:
        return await close_terminal_sessions_for_user(api_context, user_id=user_id)
    return 0
