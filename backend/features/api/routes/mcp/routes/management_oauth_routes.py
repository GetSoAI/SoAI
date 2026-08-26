"""SoAI - MCP management OAuth routes [backend/features/api/routes/mcp/routes/management_oauth_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.routes.mcp.routes import (
    management_oauth_callback_endpoints,
    management_oauth_metadata_endpoints,
    management_oauth_start_endpoints,
    management_oauth_status_endpoints,
)
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    management_oauth_start_endpoints.register_endpoints(routers.mcp)
    management_oauth_callback_endpoints.register_endpoints(routers.mcp)
    management_oauth_status_endpoints.register_endpoints(routers.mcp)
    management_oauth_metadata_endpoints.register_endpoints(routers.mcp)
