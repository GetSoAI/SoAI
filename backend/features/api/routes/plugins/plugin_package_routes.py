"""SoAI - Plugin package router registration [backend/features/api/routes/plugins/plugin_package_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.routes.plugins.plugin_package_endpoints import register_endpoints
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.plugins)
