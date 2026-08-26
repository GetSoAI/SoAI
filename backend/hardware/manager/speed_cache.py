"""SoAI - Hardware manager speed test cache state [backend/hardware/manager/speed_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.types.json import JSONDict, JSONValue

__all__ = (
    "DiskSpeedCacheState",
    "NetworkSpeedCacheState",
)


@dataclass(slots=True)
class DiskSpeedCacheState:
    cached_speed: JSONDict | None = None
    cache_timestamp: float = 0.0

    def get(self) -> tuple[JSONDict | None, float]:
        return (self.cached_speed, self.cache_timestamp)

    def set(self, snapshot: JSONDict | None, *, cached_at: float) -> None:
        self.cached_speed = snapshot
        self.cache_timestamp = float(cached_at)


@dataclass(slots=True)
class NetworkSpeedCacheState:
    cached_speed: JSONDict = field(default_factory=dict[str, JSONValue])
    cache_timestamp: float = 0.0
    loaded_from_db: bool = False

    def get(self) -> tuple[JSONDict, float, bool]:
        return (self.cached_speed, self.cache_timestamp, self.loaded_from_db)

    def set(self, snapshot: JSONDict, *, cached_at: float, loaded_from_db: bool) -> None:
        self.cached_speed = snapshot
        self.cache_timestamp = float(cached_at)
        self.loaded_from_db = bool(loaded_from_db)
