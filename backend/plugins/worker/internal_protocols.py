"""SoAI - Plugin worker internal protocols [backend/plugins/worker/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from core.plugins.protocols_instance import PluginSurfaceMetadataProtocol
from core.types.json import JSONDict

__all__ = (
    "DownloadReservationScopeFactoryProtocol",
    "DownloadReservationScopeProtocol",
    "ProxySurfaceTarget",
)


class DownloadReservationScopeProtocol(Protocol):
    def __enter__(self) -> tuple[str, str] | None: ...
    def __exit__(
        self,
        typ: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class DownloadReservationScopeFactoryProtocol(Protocol):
    def __call__(
        self,
        worker_id: int,
        plan: JSONDict | None,
    ) -> DownloadReservationScopeProtocol: ...


class ProxySurfaceTarget(PluginSurfaceMetadataProtocol, Protocol): ...
