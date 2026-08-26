"""SoAI - Conversation absolute-paths preview resolution [backend/features/api/routes/webui/absolute_paths_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.webui.absolute_path_resolution import resolve_one_absolute_path
from features.api.routes.webui.absolute_paths_contracts import (
    AbsolutePathsResolveError,
    AbsolutePathsResolveOk,
    AbsolutePathsResolveRequest,
    AbsolutePathsResolveResponse,
)
from features.api.routes.webui.absolute_paths_resolution_state import (
    AbsolutePathsResolutionState,
)
from features.api.runtime.conversation_workspace_scope import (
    build_conversation_workspace_scope,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.user_types import CurrentUser

__all__ = ("resolve_absolute_paths_payload",)


async def resolve_absolute_paths_payload(
    *,
    body: AbsolutePathsResolveRequest,
    current_user: CurrentUser,
    conversation_record: JSONDict,
    api_context: ApiContext,
    logger: LoggerProtocol,
) -> JSONDict:
    state = _build_resolution_state(
        current_user=current_user,
        conversation_record=conversation_record,
        api_context=api_context,
        logger=logger,
    )
    results: list[AbsolutePathsResolveOk | AbsolutePathsResolveError] = []
    for raw_path in body.paths:
        result = await resolve_one_absolute_path(state=state, raw_path=raw_path)
        results.append(result)
    payload = AbsolutePathsResolveResponse(
        results=results,
        override_workspace_path=state.override_workspace_path,
        override_is_valid=state.override_is_valid,
        override_validation_message=state.override_validation_message,
        effective_workspace_path=state.effective_root_real,
    )
    return payload.model_dump()


def _build_resolution_state(
    *,
    current_user: CurrentUser,
    conversation_record: JSONDict,
    api_context: ApiContext,
    logger: LoggerProtocol,
) -> AbsolutePathsResolutionState:
    scope = build_conversation_workspace_scope(
        current_user=current_user,
        conversation_record=conversation_record,
        api_context=api_context,
    )
    return AbsolutePathsResolutionState(
        file_explorer_core=scope.file_explorer_core,
        user_root_scope=scope.user_root_scope,
        effective_root_real=scope.effective_root_real,
        override_workspace_path=scope.override_workspace_path,
        override_is_valid=scope.override_is_valid,
        override_validation_message=scope.override_validation_message,
        logger=logger,
    )
