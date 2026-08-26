"""SoAI - Disk space snapshot implementation [backend/hardware/storage/snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("DiskSpaceSnapshot",)


class DiskSpaceSnapshot:
    __slots__ = ("check_path", "free_bytes", "mount_point", "total_bytes", "used_bytes")

    def __init__(
        self,
        *,
        check_path: str,
        mount_point: str | None,
        total_bytes: int,
        free_bytes: int,
        used_bytes: int,
    ) -> None:
        self.check_path = check_path
        self.mount_point = mount_point
        self.total_bytes = total_bytes
        self.free_bytes = free_bytes
        self.used_bytes = used_bytes

    @property
    def percent_used(self) -> float | None:
        if self.total_bytes <= 0:
            return None
        try:
            return round(float(self.used_bytes) / float(self.total_bytes) * 100.0, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
