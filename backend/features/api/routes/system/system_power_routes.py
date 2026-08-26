"""SoAI - System power management route registrar [backend/features/api/routes/system/system_power_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.routes.system.system_power_application_routes import (
    register_application_power_routes,
)
from features.api.routes.system.system_power_host_routes import (
    register_host_power_routes,
)
from features.api.routes.system.system_power_operation_routes import (
    register_power_operation_routes,
)
from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    register_application_power_routes(routers)
    register_host_power_routes(routers)
    register_power_operation_routes(routers)
