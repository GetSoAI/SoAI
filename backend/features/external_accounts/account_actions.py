"""SoAI - Shared external account action assembly [backend/features/external_accounts/account_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("resolve_domain_account_supported_actions",)


def resolve_domain_account_supported_actions(
    *,
    auth_type: str,
    ready: bool,
    ready_actions: tuple[str, ...],
) -> list[str]:
    actions = ["delete"]
    if ready:
        actions.extend(ready_actions)
    if auth_type == "oauth2":
        actions.extend(("oauth_connect", "oauth_clear"))
    return actions
