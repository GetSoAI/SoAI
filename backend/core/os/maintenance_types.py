"""SoAI - Core OS maintenance types [backend/core/os/maintenance_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.timing.epoch import epoch_ms

__all__ = (
    "LogEntry",
    "MaintenanceStatusSnapshot",
    "SystemdServiceStatus",
    "TimeSyncStatus",
)


@dataclass(frozen=True, slots=True)
class MaintenanceStatusSnapshot:
    time_sync_active: bool
    time_sync_server: str | None
    system_uptime_ms: int
    load_average: tuple[float, float, float]
    timestamp_ms: int = field(default_factory=epoch_ms)


@dataclass(frozen=True, slots=True)
class SystemdServiceStatus:
    name: str
    description: str | None
    load_state: str | None
    active_state: str | None
    sub_state: str | None
    unit_file_state: str | None
    main_pid: int | None
    memory_current: int | None


@dataclass(frozen=True, slots=True)
class TimeSyncStatus:
    active: bool
    synchronized: bool
    server: str | None
    ntp_service: str
    system_time: str | None
    rtc_time: str | None
    timezone: str | None
    timestamp_ms: int = field(default_factory=epoch_ms)


@dataclass(frozen=True, slots=True)
class LogEntry:
    timestamp_ms: int
    priority: int
    unit: str | None
    message: str
    hostname: str | None = None
