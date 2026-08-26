"""SoAI - Router dependency configuration for API endpoints [backend/features/api/lifecycle/router_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from fastapi import Depends, params
from fastapi.routing import APIRoute

from core.state.access import AccessAction
from core.system_api.request_paths import (
    PublicRequestSurface,
    resolve_public_request_surface,
)
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.feature_flags import (
    require_mcp_feature_enabled,
)
from features.api.runtime.restart import check_restart_status

__all__ = (
    "configure_registered_route_dependencies",
    "configure_router_dependencies",
)


def _dependency_exists(
    dependencies: list[params.Depends],
    dependency: params.Depends,
) -> bool:
    dependency_callable = dependency.dependency
    return any(existing.dependency is dependency_callable for existing in dependencies)


def _append_dependency_if_missing(
    dependencies: list[params.Depends],
    dependency: params.Depends,
) -> None:
    if _dependency_exists(dependencies, dependency):
        return
    dependencies.append(dependency)


def _extend_dependencies_if_missing(
    dependencies: list[params.Depends],
    new_dependencies: Sequence[params.Depends],
) -> None:
    for dependency in new_dependencies:
        _append_dependency_if_missing(dependencies, dependency)


def _is_acl_dependency(dependency: params.Depends) -> bool:
    dependency_callable = dependency.dependency
    if dependency_callable is None:
        return False
    try:
        dependency_name = dependency_callable.__name__
    except AttributeError:
        dependency_name = ""
    try:
        dependency_module = dependency_callable.__module__
    except AttributeError:
        dependency_module = ""
    return dependency_name == "_dependency" and dependency_module.endswith(".acl_enforcement")


def _route_has_acl_dependency(route: APIRoute) -> bool:
    return any(_is_acl_dependency(dependency) for dependency in route.dependencies)


def _configure_webui_route_dependencies(routers: ApiRouters) -> None:
    auth_cookie_dependencies = require_action_dependencies(AccessAction.AUTH_COOKIE)
    for route in routers.webui.routes:
        if not isinstance(route, APIRoute):
            continue
        if any(
            resolve_public_request_surface(route.path, method) is PublicRequestSurface.API
            for method in route.methods or ()
        ):
            continue
        if _route_has_acl_dependency(route):
            continue
        _extend_dependencies_if_missing(route.dependencies, auth_cookie_dependencies)


def configure_router_dependencies(routers: ApiRouters) -> None:
    restart_dep = Depends(check_restart_status)
    mcp_enabled_dep = Depends(require_mcp_feature_enabled)
    _append_dependency_if_missing(routers.openai_files.dependencies, restart_dep)
    _append_dependency_if_missing(routers.anthropic_public.dependencies, restart_dep)
    _append_dependency_if_missing(routers.webui.dependencies, restart_dep)
    _append_dependency_if_missing(routers.openai_public.dependencies, restart_dep)
    _append_dependency_if_missing(routers.mcp.dependencies, mcp_enabled_dep)
    _append_dependency_if_missing(routers.mcp_streamable_http.dependencies, mcp_enabled_dep)


def configure_registered_route_dependencies(routers: ApiRouters) -> None:
    _configure_webui_route_dependencies(routers)
