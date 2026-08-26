"""SoAI - API runtime access to Starlette app state [backend/features/api/runtime/app_state_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.datastructures import State

from core.errors.exceptions import StateError
from features.api.runtime.internal_protocols import HasAppProtocol

__all__ = ("require_app_state",)


def require_app_state(holder: HasAppProtocol) -> State:
    app_obj = holder.app
    app_state = app_obj.state
    if not isinstance(app_state, State):
        raise StateError("ASGI application runtime state is not Starlette state.")
    return app_state
