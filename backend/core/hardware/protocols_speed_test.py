"""SoAI - Hardware speed test protocol definitions [backend/core/hardware/protocols_speed_test.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.hardware.protocols import DatabaseHardwareProtocol
    from core.hardware.speed_test.disk_speed_test_types import SpeedTestSnapshot
    from core.hardware.speed_test.types import NetworkSpeedTestSnapshot
    from core.types.protocols import HttpClientProtocol

__all__ = ()


class NetworkSpeedTestServiceProtocol(Protocol):
    async def get_snapshot(
        self,
        http_client: HttpClientProtocol,
        url: str | None = None,
        sample_bytes: int | None = None,
        cache_seconds: float | None = None,
    ) -> NetworkSpeedTestSnapshot: ...


class DiskSpeedTestServiceProtocol(Protocol):
    async def get_snapshot(
        self,
        storage_path: str,
        database_hardware: DatabaseHardwareProtocol | None,
        cache_seconds: float,
        sample_bytes: int,
    ) -> SpeedTestSnapshot: ...

    async def get_cached_snapshot(
        self,
        storage_path: str,
        database_hardware: DatabaseHardwareProtocol | None,
        cache_seconds: float,
    ) -> SpeedTestSnapshot | None: ...
