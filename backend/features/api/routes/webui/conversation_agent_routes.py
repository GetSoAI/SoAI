"""SoAI - Agent WebUI route registration [backend/features/api/routes/webui/conversation_agent_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.routes.webui.conversation_agent_cancel_route import (
    register_cancel_route,
)
from features.api.routes.webui.conversation_agent_compaction.routes import (
    register_compaction_route,
)
from features.api.routes.webui.conversation_agent_plan_route import register_plan_route
from features.api.routes.webui.conversation_agent_shell_stop_route import (
    register_shell_stop_route,
)
from features.api.routes.webui.conversation_agent_todo_route import register_todo_route
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    register_cancel_route(routers)
    register_compaction_route(routers)
    register_shell_stop_route(routers)
    register_todo_route(routers)
    register_plan_route(routers)
