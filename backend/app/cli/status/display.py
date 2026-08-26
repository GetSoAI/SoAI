"""SoAI - CLI status output [backend/app/cli/status/display.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import sys

import psutil

from app.cli.instance_control_pid import resolve_pid_file_path
from app.cli.status.config_summary_reader import read_config_summary_quick
from app.cli.status.formatting import (
    format_load_average,
    format_uptime,
)
from app.cli.status.network import (
    get_listening_endpoints_quick,
    list_candidate_api_hosts,
)
from app.cli.status.nvidia_gpu import get_gpu_info_nvidia_quick
from app.cli.status.process_info import get_process_info_quick
from app.cli.status.storage import get_storage_quick
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.formatting.bytes import format_bytes_gb_fixed, format_bytes_mb_fixed
from core.meta.version import __version__
from core.network.urls import build_host_port_url
from core.runtime.instance_record import read_verified_runtime_instance_record
from hardware.info_memory import get_memory_info

__all__ = ("display_enhanced_status",)

OPERATION = "app.cli.status.display_enhanced_status"


def display_enhanced_status(
    base_dir: str,
    pid: int,
    logger: logging.Logger,
    *,
    expected_edition: str,
) -> None:
    try:
        logger.info(
            "Version: %s, Python %d.%d",
            __version__,
            sys.version_info.major,
            sys.version_info.minor,
        )

        config_summary = read_config_summary_quick(base_dir)
        runtime_record = read_verified_runtime_instance_record(
            resolve_pid_file_path(base_dir, logger),
            base_dir=base_dir,
            expected_edition=expected_edition,
            expected_pid=pid,
        )
        runtime_api_endpoint = runtime_record.api_endpoint if runtime_record is not None else None
        listen_port = (
            runtime_api_endpoint.effective_port if runtime_api_endpoint is not None else None
        )
        listening_endpoints = get_listening_endpoints_quick(pid, port=listen_port)

        if runtime_api_endpoint is not None:
            candidate_hosts = list_candidate_api_hosts(
                bind_host=runtime_api_endpoint.bind_host,
            )
            urls = ", ".join(
                build_host_port_url(
                    runtime_api_endpoint.scheme,
                    candidate,
                    runtime_api_endpoint.effective_port,
                )
                for candidate in candidate_hosts
            )
            logger.info(
                "API: preferred port %s, effective port %s%s. URLs: %s",
                runtime_api_endpoint.preferred_port,
                runtime_api_endpoint.effective_port,
                " (automatic fallback active)" if runtime_api_endpoint.fallback_active else "",
                urls,
            )
        else:
            logger.info("API: runtime endpoint has not been published.")

        if config_summary:
            stay_offline = config_summary.stay_offline
            offline_label = "unknown" if stay_offline is None else ("on" if stay_offline else "off")
            webui_label = (
                "enabled"
                if config_summary.webui_enabled
                else ("disabled" if config_summary.webui_enabled is False else "unknown")
            )
            auto_open_label = (
                "unknown"
                if config_summary.webui_auto_open_browser is None
                else ("on" if config_summary.webui_auto_open_browser else "off")
            )
            logger.info(
                "Config: SYSTEM.RUNTIME.STAY_OFFLINE=%s, WEBUI=%s host=%s path=%s auto_open=%s, DISCOVERY_HOST=%s",
                offline_label,
                webui_label,
                config_summary.webui_host or "unknown",
                config_summary.webui_path or "unknown",
                auto_open_label,
                config_summary.system_api_discovery_host or "unknown",
            )

        _ = listening_endpoints

        process_info = get_process_info_quick(pid)
        memory_info = get_memory_info()
        gpu_info = get_gpu_info_nvidia_quick()
        storage_info = get_storage_quick(base_dir)

        if process_info:
            logger.info(
                "Process: %d MB RSS, %.1f%% CPU, %d threads, uptime %s",
                int(process_info.rss_mb),
                process_info.cpu_percent,
                process_info.num_threads,
                format_uptime(process_info.uptime_ms),
            )

        if memory_info:
            total_gb_raw = memory_info.get("total_gb", 0.0)
            used_gb_raw = memory_info.get("used_gb", 0.0)
            total_gb = float(total_gb_raw) if isinstance(total_gb_raw, int | float) else 0.0
            used_gb = float(used_gb_raw) if isinstance(used_gb_raw, int | float) else 0.0
            available_gb = total_gb - used_gb
            physical_cores = psutil.cpu_count(logical=False) or 0
            logger.info(
                "System:  %.1f / %.1f GB RAM (%.1f GB available), %d cores%s",
                used_gb,
                total_gb,
                available_gb,
                physical_cores,
                format_load_average(),
            )

        if gpu_info:
            for gpu in gpu_info:
                logger.info(
                    "GPU %d:   %s - %d%% util, %d / %d MB VRAM, %d°C",
                    gpu.index,
                    gpu.name,
                    int(gpu.utilization_percent),
                    int(gpu.memory_used_mb),
                    int(gpu.memory_total_mb),
                    int(gpu.temperature_c),
                )

        if storage_info:
            logger.info(
                "Storage: %s DB, %s log, %s / %s free disk",
                format_bytes_mb_fixed(storage_info.db_size_bytes),
                format_bytes_mb_fixed(storage_info.log_size_bytes),
                format_bytes_gb_fixed(storage_info.disk_free_bytes),
                format_bytes_gb_fixed(storage_info.disk_total_bytes),
            )

    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to display enhanced status (non-critical).",
            operation=OPERATION,
            level="debug",
        )
