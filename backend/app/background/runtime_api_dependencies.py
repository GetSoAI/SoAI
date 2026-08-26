"""SoAI - Background access to API dependencies [backend/app/background/runtime_api_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from features.api.runtime.container.types import ApiDependencies

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeStateStoreProtocol

__all__ = ("resolve_api_dependencies_from_runtime",)


async def resolve_api_dependencies_from_runtime(
    runtime_state: RuntimeStateStoreProtocol,
) -> ApiDependencies:
    await runtime_state.startup_ready_event.wait()
    fastapi_app = runtime_state.fastapi_app
    if fastapi_app is None:
        raise StateError("FastAPI app is unavailable to background services.")
    try:
        api_dependencies = fastapi_app.state.api_dependencies
    except AttributeError as exception:
        raise StateError("API dependencies are unavailable to background services.") from exception
    if not isinstance(api_dependencies, ApiDependencies):
        raise StateError("API dependencies are unavailable to background services.")
    return api_dependencies
