"""SoAI - API runtime task registry resolution [backend/features/api/runtime/task_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.protocols import RequestProtocol
from core.tasks.protocols import TaskRegistryProtocol
from features.api.runtime.container.types import ApiDependencies
from features.api.runtime.errors import raise_task_registry_unavailable

__all__ = ("require_task_registry_or_raise",)


async def require_task_registry_or_raise(
    request: RequestProtocol,
    api_dependencies: ApiDependencies,
) -> TaskRegistryProtocol:
    registry = api_dependencies.task_registry
    if registry is None:
        raise_task_registry_unavailable(request)
    return registry
