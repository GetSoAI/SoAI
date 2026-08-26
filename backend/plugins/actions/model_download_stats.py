"""SoAI - Download statistics recording for model downloads [backend/plugins/actions/model_download_stats.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ParsedDownloadStats",
    "parse_download_stats",
    "record_download_speed",
)

LOGGER_NAME = "SoAI.plugins.actions.model_download_stats"
OPERATION = "plugin_actions.record_download_speed"


MIN_BYTES_FOR_STATS = 1_048_576
MIN_DURATION_FOR_STATS_MS = 1000


@dataclass(frozen=True, slots=True)
class ParsedDownloadStats:
    bytes_downloaded: int
    duration_ms: int
    bytes_per_second: float
    is_valid: bool


def parse_download_stats(download_stats: JSONDict | None) -> ParsedDownloadStats:
    if not download_stats:
        return ParsedDownloadStats(
            bytes_downloaded=0,
            duration_ms=0,
            bytes_per_second=0.0,
            is_valid=False,
        )
    bytes_downloaded_value = download_stats.get("bytes_downloaded", 0)
    duration_ms_value = download_stats.get("duration_ms", 0)
    bytes_per_second_value = download_stats.get("bytes_per_second", 0.0)
    bytes_downloaded = (
        int(bytes_downloaded_value)
        if isinstance(bytes_downloaded_value, int | float)
        and not isinstance(bytes_downloaded_value, bool)
        else 0
    )
    duration_ms = (
        int(duration_ms_value)
        if isinstance(duration_ms_value, int | float) and not isinstance(duration_ms_value, bool)
        else 0
    )
    bytes_per_second = (
        float(bytes_per_second_value)
        if isinstance(bytes_per_second_value, int | float)
        and not isinstance(bytes_per_second_value, bool)
        else 0.0
    )
    is_valid = (
        bytes_downloaded > MIN_BYTES_FOR_STATS
        and duration_ms >= MIN_DURATION_FOR_STATS_MS
        and bytes_per_second > 0
    )
    return ParsedDownloadStats(
        bytes_downloaded=bytes_downloaded,
        duration_ms=duration_ms,
        bytes_per_second=bytes_per_second,
        is_valid=is_valid,
    )


async def record_download_speed(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    model_id: str,
    stats: ParsedDownloadStats,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not stats.is_valid:
        return
    try:
        await manager.dependencies.databases.hardware.save_real_download_speed(
            plugin_name,
            model_id,
            stats.bytes_downloaded,
            stats.duration_ms,
            stats.bytes_per_second,
        )
        metrics_mgr = manager.dependencies.infrastructure.metrics_manager
        update_download_speed_metrics = None
        if metrics_mgr is not None:
            try:
                update_download_speed_metrics = metrics_mgr.update_download_speed_metrics
            except AttributeError:
                update_download_speed_metrics = None
        if callable(update_download_speed_metrics):
            update_download_speed_metrics(stats.bytes_per_second, source="real_download")
        logger.info(
            "Saved real download speed: %.2f MB/s for %s",
            stats.bytes_per_second / MIN_BYTES_FOR_STATS,
            model_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to save download speed",
            operation=OPERATION,
            details={"plugin_name": plugin_name, "model_id": model_id},
            level="warning",
        )
