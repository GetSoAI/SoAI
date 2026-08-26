"""SoAI - Network speed test service [backend/core/hardware/speed_test/network_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.hardware.speed_test.types import NetworkSpeedTestSnapshot
from core.timing.constants import BACKGROUND_TIMEOUT_SEC
from core.timing.epoch import epoch_seconds_float
from core.types.protocols import HttpClientProtocol

__all__ = (
    "NetworkSpeedTestService",
    "NetworkSpeedTestServiceDependencies",
)

_NETWORK_SPEED_TEST_URL = "https://ftp.gnu.org/gnu/emacs/emacs-29.4.tar.xz"
_NETWORK_SPEED_TEST_SAMPLE_BYTES = MIB_BYTES
_SPEED_TEST_CACHE_SECONDS = 900.0


@dataclass(frozen=True, slots=True)
class NetworkSpeedTestServiceDependencies:
    default_url: str = _NETWORK_SPEED_TEST_URL
    default_sample_bytes: int = _NETWORK_SPEED_TEST_SAMPLE_BYTES
    default_cache_seconds: float = _SPEED_TEST_CACHE_SECONDS
    default_timeout: float = BACKGROUND_TIMEOUT_SEC

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NetworkSpeedTestServiceDependencies",
            default_cache_seconds=self.default_cache_seconds,
            default_sample_bytes=self.default_sample_bytes,
            default_timeout=self.default_timeout,
            default_url=self.default_url,
        )


class NetworkSpeedTestService:
    __slots__ = (
        "_default_cache_seconds",
        "_default_sample_bytes",
        "_default_timeout",
        "_default_url",
        "_lock",
        "_snapshot",
    )

    def __init__(self, deps: NetworkSpeedTestServiceDependencies) -> None:
        self._default_url: str = deps.default_url
        self._default_sample_bytes: int = deps.default_sample_bytes
        self._default_cache_seconds: float = deps.default_cache_seconds
        self._default_timeout: float = deps.default_timeout
        self._snapshot: NetworkSpeedTestSnapshot | None = None
        self._lock: asyncio.Lock | None = None

    async def get_snapshot(
        self,
        http_client: HttpClientProtocol,
        url: str | None = None,
        sample_bytes: int | None = None,
        cache_seconds: float | None = None,
    ) -> NetworkSpeedTestSnapshot:
        if http_client is None:
            raise ValidationError("HTTP client is required for network speed test.")

        effective_url = url if url is not None else self._default_url
        effective_sample_bytes = (
            sample_bytes if sample_bytes is not None else self._default_sample_bytes
        )
        effective_cache_seconds = (
            cache_seconds if cache_seconds is not None else self._default_cache_seconds
        )

        if effective_sample_bytes <= 0:
            raise ValidationError("Sample size must be positive for network speed test.")

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            cached = self._snapshot
            if effective_cache_seconds > 0:
                now_monotonic = time.monotonic()
                if (
                    cached is not None
                    and now_monotonic - cached.observed_monotonic < effective_cache_seconds
                    and cached.sample_bytes == effective_sample_bytes
                    and cached.url == effective_url
                ):
                    return cached

            start_time = time.perf_counter()
            total_bytes = 0
            async with http_client.stream(
                "GET",
                effective_url,
                follow_redirects=True,
                timeout=self._default_timeout,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    remaining = effective_sample_bytes - total_bytes
                    if remaining <= 0:
                        break
                    chunk_len = len(chunk)
                    if chunk_len >= remaining:
                        total_bytes += remaining
                        break
                    total_bytes += chunk_len

            if total_bytes <= 0:
                raise StateError("Network speed test produced no data.")

            duration = max(time.perf_counter() - start_time, 1e-06)
            bytes_per_second = total_bytes / duration

            if not math.isfinite(bytes_per_second) or bytes_per_second <= 0:
                raise StateError("Network speed test produced invalid throughput.")

            snapshot = NetworkSpeedTestSnapshot(
                observed_monotonic=time.monotonic(),
                observed_unix=epoch_seconds_float(),
                duration_ms=max(0, int(duration * 1000)),
                bytes_downloaded=int(total_bytes),
                bytes_per_second=float(bytes_per_second),
                sample_bytes=int(effective_sample_bytes),
                url=effective_url,
            )
            self._snapshot = snapshot
            return snapshot

    def invalidate_cache(self) -> None:
        self._snapshot = None
