"""SoAI - Plugin runtime support operations [backend/core/plugins/runtime_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import ensure_parent_dirs_exist
from core.filesystem.hashing import calculate_directory_hash, calculate_file_hash
from core.filesystem.size_calculation import get_path_size
from core.logging.trace import get_logger
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.protocols_runtime import PluginMetricsRuntimeProtocol
from core.timing.formatting import utc_now_iso
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "calculate_model_hash",
    "calculate_model_hash_and_metadata",
    "initialize_temp_directory",
    "open_log_file",
    "track_request",
)

LOGGER_NAME = "SoAI.core.plugins.runtime_support"


def initialize_temp_directory(config: ConfigProtocol) -> str:
    system_data_path = config.require_str("SYSTEM.PATHS.SYSTEM_DATA")
    candidate_value = config.get_str("SYSTEM.PATHS.TEMP")
    candidate = (
        candidate_value
        if isinstance(candidate_value, str) and candidate_value.strip()
        else os.path.join(system_data_path, "temp")
    )
    os.makedirs(candidate, exist_ok=True)
    return candidate


async def open_log_file(
    *,
    plugin_name: str,
    files: FilesProtocol,
    config: ConfigProtocol,
    command: Sequence[str] | None = None,
) -> io.BufferedIOBase:
    plugin_logs_path = config.get_str("PLUGINS.PATHS.PLUGIN_LOGS")
    if not isinstance(plugin_logs_path, str) or not plugin_logs_path.strip():
        raise StateError(
            "Config is missing PLUGINS.PATHS.PLUGIN_LOGS; cannot open plugin log file.",
        )
    path = files.resolve_path(os.path.join(plugin_logs_path, f"{plugin_name}.log"))
    await ensure_parent_dirs_exist([path])
    handle = await asyncio.to_thread(open, path, "ab")
    header = f"\n--- NEW SESSION: {utc_now_iso()} ---\n"
    if command:
        header += f"CMD: {' '.join(command)}\n"
    header += "---\n"
    await asyncio.to_thread(handle.write, header.encode())
    await asyncio.to_thread(handle.flush)
    return handle


@asynccontextmanager
async def track_request(
    *,
    metrics: PluginMetricsRuntimeProtocol | None,
    plugin_name: str,
    count_total: bool = True,
    record_timing: bool = True,
    record_success: bool = True,
) -> AsyncGenerator[None]:
    start_time_ms: int | None = None
    if metrics and count_total:
        metrics.increment_counter("plugins", plugin_name, "requests_total")
    if metrics and record_timing:
        start_time_ms = monotonic_ms()
    try:
        yield
    except RECOVERABLE_EXCEPTIONS:
        if metrics:
            metrics.increment_counter("plugins", plugin_name, "requests_failed")
        raise
    else:
        if metrics and record_success:
            metrics.increment_counter("plugins", plugin_name, "requests_succeeded")
    finally:
        if metrics and record_timing and (start_time_ms is not None):
            duration_ms = max(0, monotonic_ms() - start_time_ms)
            metrics.record_timing(
                "plugins",
                plugin_name,
                "timings",
                "request_latency_ms",
                duration_ms=float(duration_ms),
            )


async def calculate_model_hash(
    *,
    model_path: str,
    existing_model_info: JSONDict | None = None,
    plugin_name: str | None = None,
) -> str | None:
    content_hash, _current_size, _current_mtime = await calculate_model_hash_and_metadata(
        model_path=model_path,
        existing_model_info=existing_model_info,
        plugin_name=plugin_name,
    )
    return content_hash


async def calculate_model_hash_and_metadata(
    *,
    model_path: str,
    existing_model_info: JSONDict | None = None,
    plugin_name: str | None = None,
) -> tuple[str | None, float | None, float | None]:
    try:
        is_dir = await asyncio.to_thread(os.path.isdir, model_path)
        if not is_dir and not await asyncio.to_thread(os.path.isfile, model_path):
            return None, None, None
        stat_info = await asyncio.to_thread(os.stat, model_path)
        current_mtime = float(stat_info.st_mtime)
        current_size = await get_path_size(model_path) if is_dir else float(stat_info.st_size)
        if existing_model_info and existing_model_info.get("content_hash"):
            plugin_label = plugin_name or "unknown"
            existing_mtime = existing_model_info.get("mtime")
            existing_size = existing_model_info.get("size_bytes")
            if (
                existing_mtime is not None
                and existing_size is not None
                and current_size is not None
                and isinstance(existing_mtime, int | float | str)
                and isinstance(existing_size, int | float | str)
            ):
                try:
                    if (
                        abs(current_mtime - float(existing_mtime)) < 0.001
                        and abs(current_size - float(existing_size)) < 1e-06
                    ):
                        content_hash = existing_model_info.get("content_hash")
                        return (
                            content_hash if isinstance(content_hash, str) else None,
                            current_size,
                            current_mtime,
                        )
                except (TypeError, ValueError):
                    get_logger(LOGGER_NAME).debug(
                        "Fast path metadata type mismatch for '%s' (plugin=%s). Proceeding with full hash.",
                        os.path.basename(model_path),
                        plugin_label,
                    )
            get_logger(LOGGER_NAME).debug(
                "Fast path failed for '%s' (plugin=%s). Metadata mismatch. Proceeding with full hash.",
                os.path.basename(model_path),
                plugin_label,
            )
        return (
            await (calculate_directory_hash if is_dir else calculate_file_hash)(model_path),
            current_size,
            current_mtime,
        )
    except OSError as exception:
        get_logger(LOGGER_NAME).warning(
            "Could not access path '%s' for hashing: %s",
            model_path,
            str(exception),
        )
        return None, None, None
