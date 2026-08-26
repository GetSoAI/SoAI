"""SoAI - API runtime dependency sets for routes [backend/features/api/runtime/access_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends, Request, params

from core.errors.exceptions import ValidationError
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import require_actions
from features.api.runtime.openai_request_state import initialize_openai_request_state
from features.api.runtime.restart import check_restart_status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.state.access import AccessState

__all__ = (
    "openai_api_dependency",
    "require_action_dependencies",
    "restart_protected_dependencies",
)


@lru_cache(maxsize=256)
def _require_action_dependency_callable(
    action: AccessAction,
) -> Callable[[Request], Awaitable[AccessState]]:
    return require_actions(action)


def openai_api_dependency() -> params.Depends:
    async def dependency(request: Request) -> AccessState:
        initialize_openai_request_state(request)
        return await _require_action_dependency_callable(AccessAction.OPENAI_API)(request)

    dependency_marker: params.Depends = Depends(dependency)
    return dependency_marker


def require_action_dependencies(*actions: AccessAction) -> tuple[params.Depends, ...]:
    if not actions:
        raise ValidationError("At least one AccessAction is required.")
    return tuple(Depends(_require_action_dependency_callable(action)) for action in actions)


def restart_protected_dependencies(action: AccessAction) -> Sequence[params.Depends]:
    return (Depends(check_restart_status), Depends(_require_action_dependency_callable(action)))
