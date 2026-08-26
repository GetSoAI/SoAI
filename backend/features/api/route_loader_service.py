"""SoAI - API route loader service [backend/features/api/route_loader_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from collections.abc import Callable

    from features.api.runtime.container.api_routers import ApiRouters

__all__ = (
    "ApiRouteLoaderService",
    "ApiRouteLoaderServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class ApiRouteLoaderServiceDependencies:
    route_registrars: tuple[Callable[[ApiRouters], None], ...]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiRouteLoaderServiceDependencies",
            route_registrars=self.route_registrars,
        )


def _register_route_modules(
    registrars: Iterable[Callable[[ApiRouters], None]],
    *,
    routers: ApiRouters,
) -> None:
    for registrar in registrars:
        if not callable(registrar):
            raise StateError(
                "Route registrar must be callable.",
                operation="api_lifecycle.route_loader_service.register_routes",
            )
        try:
            registrar(routers)
        except RECOVERABLE_EXCEPTIONS as exception:
            raise StateError(
                "API route module failed during register_routes(routers).",
                cause=exception,
                operation="api_lifecycle.route_loader_service.register_routes",
            ) from exception


class ApiRouteLoaderService:
    __slots__ = ("_loaded", "_lock", "_route_registrars")

    def __init__(self, deps: ApiRouteLoaderServiceDependencies) -> None:
        self._route_registrars = deps.route_registrars
        self._loaded: bool = False
        self._lock: threading.Lock = threading.Lock()

    def load_routes(self, routers: ApiRouters) -> None:
        with self._lock:
            if self._loaded:
                return
            _register_route_modules(self._route_registrars, routers=routers)
            self._loaded = True

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._loaded
