"""SoAI - System access control policy routes [backend/features/api/routes/system/system_access_control_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.state.access import AccessAction, AccessState
from core.state.access_policy import (
    AccessPolicyOverrideError,
    AccessPolicyUpdate,
)
from core.state.access_policy_overrides import (
    build_access_policy_response,
    load_access_policy_overrides,
    merge_access_policy,
    persist_access_policy_overrides,
    validate_override_entry,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_bad_request
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.terminal_access_cleanup import (
    close_terminal_sessions_for_users_losing_access,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/access-control/policy",
        dependencies=require_action_dependencies(AccessAction.ACL_ADMIN),
    )
    async def get_access_control_policy(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        overrides = await load_access_policy_overrides(api_context.dependencies.database_plugins)
        policy = merge_access_policy(overrides)
        return JSONResponse(content=build_access_policy_response(policy, overrides))

    @routers.system.put(
        "/access-control/policy",
        dependencies=require_action_dependencies(AccessAction.ACL_ADMIN),
    )
    async def update_access_control_policy(
        request: Request,
        payload: AccessPolicyUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        previous_overrides = await load_access_policy_overrides(
            api_context.dependencies.database_plugins,
        )
        previous_policy = merge_access_policy(previous_overrides)
        overrides: dict[AccessState, frozenset[AccessAction]] = {}
        for state, actions in payload.overrides.items():
            candidate = frozenset(actions)
            try:
                overrides[state] = validate_override_entry(state, candidate)
            except AccessPolicyOverrideError as exception:
                raise_bad_request(
                    request,
                    str(exception),
                    error_type="invalid_acl_override",
                )
        policy = await persist_access_policy_overrides(
            api_context.dependencies.access_policy_cache,
            overrides,
            api_context.dependencies.database_plugins,
        )
        closed_sessions = await close_terminal_sessions_for_users_losing_access(
            api_context,
            previous_policy=previous_policy,
            next_policy=policy,
        )
        log_audit_event(
            request,
            "UPDATE_ACL_POLICY",
            "access_control",
            {
                "states": sorted(state.value for state in overrides),
                "closed_terminal_sessions": closed_sessions,
            },
        )
        return JSONResponse(content=build_access_policy_response(policy, overrides))

    @routers.system.delete(
        "/access-control/policy",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.ACL_ADMIN),
    )
    async def clear_access_control_policy(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        previous_overrides = await load_access_policy_overrides(
            api_context.dependencies.database_plugins,
        )
        previous_policy = merge_access_policy(previous_overrides)
        policy = await persist_access_policy_overrides(
            api_context.dependencies.access_policy_cache,
            None,
            api_context.dependencies.database_plugins,
        )
        closed_sessions = await close_terminal_sessions_for_users_losing_access(
            api_context,
            previous_policy=previous_policy,
            next_policy=policy,
        )
        log_audit_event(
            request,
            "RESET_ACL_POLICY",
            "access_control",
            {"closed_terminal_sessions": closed_sessions},
        )
        return create_no_content_response()
