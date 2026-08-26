"""SoAI - WebUI conversation attachment route registration [backend/features/api/routes/webui/conversation_attachments/conversation_attachment_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.routes.webui.conversation_attachments.knowledge_cancel_routes import (
    register_knowledge_attachment_cancel_route,
)
from features.api.routes.webui.conversation_attachments.knowledge_delete_routes import (
    register_knowledge_attachment_delete_routes,
)
from features.api.routes.webui.conversation_attachments.knowledge_link_routes import (
    register_knowledge_link_routes,
)
from features.api.routes.webui.conversation_attachments.knowledge_routes import (
    register_knowledge_attachment_routes,
)
from features.api.routes.webui.conversation_attachments.physical_routes import (
    register_physical_attachment_routes,
)
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    register_physical_attachment_routes(routers)
    register_knowledge_attachment_cancel_route(routers)
    register_knowledge_attachment_delete_routes(routers)
    register_knowledge_attachment_routes(routers)
    register_knowledge_link_routes(routers)
