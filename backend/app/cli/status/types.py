"""SoAI - CLI status data types [backend/app/cli/status/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

__all__ = (
    "ConfigSummary",
    "ListeningEndpoint",
    "NvidiaGpuInfo",
    "ProcessInfo",
    "StorageInfo",
)


@dataclasses.dataclass(frozen=True, slots=True)
class ProcessInfo:
    rss_mb: float
    cpu_percent: float
    num_threads: int
    uptime_ms: float


@dataclasses.dataclass(frozen=True, slots=True)
class NvidiaGpuInfo:
    index: int
    name: str
    utilization_percent: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_c: float


@dataclasses.dataclass(frozen=True, slots=True)
class StorageInfo:
    db_size_bytes: int
    log_size_bytes: int
    disk_total_bytes: int
    disk_free_bytes: int


@dataclasses.dataclass(frozen=True, slots=True)
class ConfigSummary:
    stay_offline: bool | None
    system_api_host: str | None
    system_api_port: int | None
    system_api_tls_enabled: bool | None
    system_api_discovery_host: str | None
    webui_enabled: bool | None
    webui_host: str | None
    webui_path: str | None
    webui_auto_open_browser: bool | None


@dataclasses.dataclass(frozen=True, slots=True)
class ListeningEndpoint:
    ip: str
    port: int
