"""SoAI - API route edition composition contract [backend/features/api/runtime/container/route_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter

from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("ApiRouteComposition",)


@dataclass(frozen=True, slots=True)
class ApiRouteComposition:
    host_management_router_factory: Callable[[], APIRouter] | None
    registrars: tuple[Callable[[ApiRouters], None], ...]
