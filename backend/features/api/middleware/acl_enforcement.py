"""SoAI - API access control enforcement [backend/features/api/middleware/acl_enforcement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from fastapi import Request, status

from core.errors.exceptions import ValidationError
from core.licensing.access_policy import apply_licensing_action_policy
from core.licensing.types import LicensingStatus
from core.logging.trace import get_logger
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.runtime.protocols import RequestProtocol
from core.state.access import AccessAction, AccessState
from core.state.access_policy import extract_granted_actions
from core.state.access_policy_effective import resolve_effective_actions
from core.state.access_policy_overrides import get_effective_access_policy
from core.state.repair_plane import restrict_to_repair_plane
from core.system_api.request_paths import get_scope_path
from core.types.json import JSONValue, is_json_dict
from core.users.bootstrap_state import BootstrapState
from core.webui_manager.protocols import WebUIManagerProtocol

__all__ = (
    "deny_if_licensing_restricted",
    "request_has_action",
    "require_any_actions",
    "require_actions",
    "resolve_access_state",
    "resolve_effective_actions",
    "resolve_request_effective_actions",
)

LOGGER_NAME = "SoAI.features.api.acl_enforcement"


async def resolve_access_state(
    request: RequestProtocol,
    webui_mgr: WebUIManagerProtocol,
    _database_plugins: DatabasePluginsProtocol,
) -> AccessState:
    try:
        cached = request.state.access_state
    except AttributeError:
        cached = None
    if isinstance(cached, AccessState):
        return cached
    try:
        auth_method = request.state.auth_method
    except AttributeError:
        auth_method = "none"
    try:
        user = request.state.user
    except AttributeError:
        user = None
    if auth_method == "wizard_bootstrap":
        state = AccessState.UNINITIALIZED
    elif auth_method == "openai_api_key":
        state = AccessState.STANDARD
    elif (auth_method == "mcp_pat" and is_json_dict(user)) or (
        auth_method in {"jwt_cookie", "jwt_cookie_rotation_recovery"} and is_json_dict(user)
    ):
        if user.get("is_admin") is True:
            state = AccessState.ADMIN
        else:
            state = AccessState.STANDARD
    else:
        bootstrap_state = await _resolve_request_bootstrap_state(request, webui_mgr)
        if bootstrap_state is BootstrapState.UNINITIALIZED:
            state = AccessState.UNINITIALIZED
        else:
            state = AccessState.ANONYMOUS
    request.state.access_state = state
    return state


async def _resolve_request_bootstrap_state(
    request: RequestProtocol,
    webui_manager: WebUIManagerProtocol,
) -> BootstrapState:
    try:
        cached_state = request.state.bootstrap_state
    except AttributeError:
        cached_state = None
    if isinstance(cached_state, BootstrapState):
        return cached_state
    bootstrap_state = await webui_manager.get_bootstrap_state()
    request.state.bootstrap_state = bootstrap_state
    return bootstrap_state


def _record_acl_denial(
    request: Request,
    state: AccessState,
    missing: frozenset[AccessAction],
    log_callback: Callable[[Request, str, str, Mapping[str, JSONValue] | None], None],
) -> None:
    path = get_scope_path(request.scope)
    detail = {
        "state": state.value,
        "missing_actions": sorted(action.value for action in missing),
        "path": path,
        "method": request.method,
    }
    get_logger(LOGGER_NAME).warning(
        "ACL denial for %s %s with state %s missing %s",
        request.method,
        path,
        state.value,
        detail["missing_actions"],
    )
    log_callback(request, "ACL_DENIED", path, detail)


def _store_context_access_actions(
    request: RequestProtocol,
    effective_actions: frozenset[AccessAction],
) -> None:
    try:
        context = request.state.context
    except AttributeError:
        return
    if context is not None:
        context.access_actions = effective_actions


async def resolve_request_effective_actions(
    request: RequestProtocol,
) -> frozenset[AccessAction]:
    api_dependencies = request.app.state.api_dependencies
    state = await resolve_access_state(
        request,
        api_dependencies.webui_manager,
        api_dependencies.database_plugins,
    )
    granted_actions = extract_granted_actions(request)
    auth_method = request.state.auth_method
    policy = await get_effective_access_policy(
        api_dependencies.access_policy_cache,
        api_dependencies.database_plugins,
    )
    allowed = policy.get(state, frozenset())
    effective_actions = resolve_effective_actions(
        auth_method=auth_method,
        granted_actions=granted_actions,
        allowed_actions=allowed,
    )
    licensing_status = await api_dependencies.licensing_service.resolved_status()
    request.state.licensing_status = licensing_status
    effective_actions = apply_licensing_action_policy(effective_actions, licensing_status)
    bootstrap_state = await _resolve_request_bootstrap_state(
        request, api_dependencies.webui_manager
    )
    if bootstrap_state is BootstrapState.INTEGRITY_ERROR:
        effective_actions = restrict_to_repair_plane(effective_actions)
    request.state.effective_access_actions = effective_actions
    _store_context_access_actions(request, effective_actions)
    return effective_actions


async def request_has_action(request: RequestProtocol, action: AccessAction) -> bool:
    effective_actions = await resolve_request_effective_actions(request)
    return action in effective_actions


def deny_if_licensing_restricted(request: Request) -> None:
    try:
        licensing_status: LicensingStatus | None = request.state.licensing_status
    except AttributeError:
        return
    if licensing_status is None or not licensing_status.requires_repair_plane:
        return
    api_dependencies = request.app.state.api_dependencies
    api_dependencies.acl_dependency_context.raise_api_error(
        request,
        status.HTTP_403_FORBIDDEN,
        "licensing_restricted",
        "Licensing recovery is required before this operation can run.",
        extra={"reason": licensing_status.state},
    )


def require_actions(
    *actions: AccessAction,
) -> Callable[[Request], Awaitable[AccessState]]:
    required = frozenset(actions)
    if not required:
        raise ValidationError("require_actions must receive at least one AccessAction.")

    async def _dependency(request: Request) -> AccessState:
        api_dependencies = request.app.state.api_dependencies
        acl_context = api_dependencies.acl_dependency_context
        log_callback = acl_context.log_audit_event
        raise_api_error = acl_context.raise_api_error
        state = await resolve_access_state(
            request,
            api_dependencies.webui_manager,
            api_dependencies.database_plugins,
        )
        effective_actions = await resolve_request_effective_actions(request)
        if required.issubset(effective_actions):
            return state
        missing = required.difference(effective_actions)
        if missing:
            deny_if_licensing_restricted(request)
            _record_acl_denial(request, state, missing, log_callback)
            raise_api_error(
                request,
                status.HTTP_403_FORBIDDEN,
                "forbidden_error",
                "You are not authorized to perform this action.",
            )
        return state

    return _dependency


def require_any_actions(
    *actions: AccessAction,
) -> Callable[[Request], Awaitable[AccessState]]:
    required = frozenset(actions)
    if not required:
        raise ValidationError("require_any_actions must receive at least one AccessAction.")

    async def _dependency(request: Request) -> AccessState:
        api_dependencies = request.app.state.api_dependencies
        state = await resolve_access_state(
            request,
            api_dependencies.webui_manager,
            api_dependencies.database_plugins,
        )
        effective_actions = await resolve_request_effective_actions(request)
        if not required.isdisjoint(effective_actions):
            return state
        acl_context = api_dependencies.acl_dependency_context
        deny_if_licensing_restricted(request)
        _record_acl_denial(request, state, required, acl_context.log_audit_event)
        acl_context.raise_api_error(
            request,
            status.HTTP_403_FORBIDDEN,
            "forbidden_error",
            "You are not authorized to perform this action.",
        )
        raise ValidationError("ACL denial handler returned unexpectedly.")

    return _dependency
