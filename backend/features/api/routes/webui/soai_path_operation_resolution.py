"""SoAI - Conversation SoAI path operation resolution [backend/features/api/routes/webui/soai_path_operation_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import JSONResponse

from core.errors.exceptions import SecurityError, ValidationError
from core.files.workspace_virtual_paths import (
    user_virtual_path_from_conversation_virtual_path,
)
from features.api.routes.webui.soai_path_operation_scope import (
    conversation_soai_path_scope,
)
from features.api.routes.webui.soai_path_operation_validation import (
    SoaiPathOperationRequest,
    canonical_soai_path_part,
    no_store_headers,
    source_reference_value,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.conversation_workspace_scope import (
        ConversationWorkspaceScope,
    )

__all__ = (
    "ResolvedSoaiPath",
    "SoaiPathRouteTarget",
    "resolve_soai_path_for_request",
    "resolve_soai_path_route_target",
    "unavailable_soai_path_response",
    "user_virtual_path_for_soai_path",
)


@dataclass(frozen=True, slots=True)
class ResolvedSoaiPath:
    scope: ConversationWorkspaceScope
    canonical: JSONDict


@dataclass(frozen=True, slots=True)
class SoaiPathRouteTarget:
    request: Request
    conv_id: str
    body: SoaiPathOperationRequest
    current_user: CurrentUser
    api_context: ApiContext


def unavailable_soai_path_response() -> JSONResponse:
    return JSONResponse(content={"state": "unavailable"}, headers=no_store_headers())


async def _canonical_for_request(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> tuple[ConversationWorkspaceScope, JSONDict]:
    scope = await conversation_soai_path_scope(
        request=request,
        conv_id=conv_id,
        current_user=current_user,
        api_context=api_context,
    )
    return scope, canonical_soai_path_part(scope, body)


async def resolve_soai_path_for_request(
    *,
    request: Request,
    conv_id: str,
    body: SoaiPathOperationRequest,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> ResolvedSoaiPath | JSONResponse:
    try:
        scope, canonical = await _canonical_for_request(
            request=request,
            conv_id=conv_id,
            body=body,
            current_user=current_user,
            api_context=api_context,
        )
    except (OSError, SecurityError, ValidationError):
        return unavailable_soai_path_response()
    return ResolvedSoaiPath(scope=scope, canonical=canonical)


async def resolve_soai_path_route_target(
    target: SoaiPathRouteTarget,
) -> ResolvedSoaiPath | JSONResponse:
    return await resolve_soai_path_for_request(
        request=target.request,
        conv_id=target.conv_id,
        body=target.body,
        current_user=target.current_user,
        api_context=target.api_context,
    )


def user_virtual_path_for_soai_path(
    scope: ConversationWorkspaceScope,
    canonical: JSONDict,
) -> str:
    return user_virtual_path_from_conversation_virtual_path(
        user_root=scope.user_root_scope.root_path,
        effective_workspace_root=scope.effective_root_real,
        conversation_virtual_path=source_reference_value(canonical),
        error_cls=ValidationError,
    )
