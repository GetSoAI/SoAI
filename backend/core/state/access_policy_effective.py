"""SoAI - Core ACL effective-action resolution [backend/core/state/access_policy_effective.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.access import AccessAction

__all__ = ("resolve_effective_actions",)


def _strip_auth_cookie_action(actions: frozenset[AccessAction]) -> frozenset[AccessAction]:
    if AccessAction.AUTH_COOKIE not in actions:
        return actions
    return frozenset(action for action in actions if action != AccessAction.AUTH_COOKIE)


def resolve_effective_actions(
    *,
    auth_method: str,
    granted_actions: frozenset[AccessAction],
    allowed_actions: frozenset[AccessAction],
) -> frozenset[AccessAction]:
    normalized_granted = granted_actions
    normalized_allowed = allowed_actions
    if auth_method not in {"jwt_cookie", "jwt_cookie_rotation_recovery"}:
        normalized_granted = _strip_auth_cookie_action(normalized_granted)
        normalized_allowed = _strip_auth_cookie_action(normalized_allowed)
    if auth_method == "openai_api_key":
        return normalized_granted
    if auth_method == "mcp_pat":
        return normalized_granted.intersection(normalized_allowed)
    if auth_method == "jwt_cookie_rotation_recovery":
        return normalized_granted
    return normalized_granted | normalized_allowed
