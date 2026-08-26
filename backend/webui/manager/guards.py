"""SoAI - WebUI authentication guard bundle [backend/webui/manager/guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.clamped_numeric import read_config_nonnegative_int
from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.wallpaper.protocols import AuthGuardProtocol
from webui.manager.auth_guard import AuthFailureGuard
from webui.manager.durable_auth_guard import DurableAuthFailureGuard

__all__ = (
    "AuthGuardBundle",
    "build_auth_guards",
)


@dataclass(frozen=True, slots=True)
class AuthGuardBundle:
    openai_auth_guard: AuthGuardProtocol
    mcp_pat_auth_guard: AuthGuardProtocol
    webui_login_guard: AuthGuardProtocol
    identity_mutation_guard: AuthGuardProtocol


def build_auth_guards(
    config: ConfigProtocol,
    database_core: DatabaseCoreProtocol | None,
) -> AuthGuardBundle:
    openai_window_seconds = read_config_nonnegative_int(
        config,
        "API.OPENAI.SECURITY.AUTH_FAILURE_RATELIMIT.WINDOW_SECONDS",
        60,
    )
    openai_failure_limit = read_config_nonnegative_int(
        config,
        "API.OPENAI.SECURITY.AUTH_FAILURE_RATELIMIT.MAX_FAILURES",
        5,
    )
    webui_window_seconds = read_config_nonnegative_int(
        config,
        "SERVER.WEBUI.LOGIN_SECURITY.AUTH_FAILURE_RATELIMIT.WINDOW_SECONDS",
        300,
    )
    webui_failure_limit = read_config_nonnegative_int(
        config,
        "SERVER.WEBUI.LOGIN_SECURITY.AUTH_FAILURE_RATELIMIT.MAX_FAILURES",
        10,
    )
    mcp_window_seconds = read_config_nonnegative_int(
        config,
        "TOOLS.MCP.SECURITY.AUTH_FAILURE_RATELIMIT.WINDOW_SECONDS",
        60,
    )
    mcp_failure_limit = read_config_nonnegative_int(
        config,
        "TOOLS.MCP.SECURITY.AUTH_FAILURE_RATELIMIT.MAX_FAILURES",
        5,
    )
    identity_window_seconds = 60
    identity_attempt_limit = 120
    if database_core is not None:
        return AuthGuardBundle(
            openai_auth_guard=DurableAuthFailureGuard(
                database_core,
                window_seconds=openai_window_seconds,
                max_failures=openai_failure_limit,
            ),
            mcp_pat_auth_guard=DurableAuthFailureGuard(
                database_core,
                window_seconds=mcp_window_seconds,
                max_failures=mcp_failure_limit,
            ),
            webui_login_guard=DurableAuthFailureGuard(
                database_core,
                window_seconds=webui_window_seconds,
                max_failures=webui_failure_limit,
            ),
            identity_mutation_guard=DurableAuthFailureGuard(
                database_core,
                window_seconds=identity_window_seconds,
                max_failures=identity_attempt_limit,
            ),
        )
    return AuthGuardBundle(
        openai_auth_guard=AuthFailureGuard(openai_window_seconds, openai_failure_limit),
        mcp_pat_auth_guard=AuthFailureGuard(mcp_window_seconds, mcp_failure_limit),
        webui_login_guard=AuthFailureGuard(webui_window_seconds, webui_failure_limit),
        identity_mutation_guard=AuthFailureGuard(identity_window_seconds, identity_attempt_limit),
    )
