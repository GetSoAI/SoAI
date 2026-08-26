"""SoAI - WebUI terminal access policy route [backend/features/api/routes/webui/terminal_policy_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypedDict

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import request_has_action
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


class TerminalPolicyResponse(TypedDict):
    can_access_terminal: bool
    admin_count: int
    policy_revision: str


async def _build_terminal_policy_response(
    request: Request,
    api_context: ApiContext,
) -> TerminalPolicyResponse:
    admin_count = await api_context.dependencies.database_users.count_human_admins()
    can_access_terminal = await request_has_action(request, AccessAction.TERMINAL_USE)
    return {
        "can_access_terminal": can_access_terminal,
        "admin_count": admin_count,
        "policy_revision": (f"terminal-use:{int(can_access_terminal)}:admin-count:{admin_count}"),
    }


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/terminal/policy",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def get_terminal_policy(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return JSONResponse(content=await _build_terminal_policy_response(request, api_context))
