"""SoAI - API subsystem internal Protocols [backend/features/api/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from features.api.runtime.container.api_routers import ApiRouters

__all__ = ("ApiRouteLoaderServiceProtocol",)


class ApiRouteLoaderServiceProtocol(Protocol):
    def load_routes(self, routers: ApiRouters) -> None: ...

    @property
    def is_loaded(self) -> bool: ...
