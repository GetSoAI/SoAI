"""SoAI - Lifecycle signaling for restart and shutdown [backend/app/lifecycle/signals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.internal_protocols import BannerSystemProtocol
from core.logging.protocols import LoggerProtocol
from core.runtime.protocols import RuntimeStateStoreProtocol

__all__ = (
    "initiate_restart_signal",
    "initiate_shutdown_signal",
    "require_runtime_restart",
    "request_runtime_restart",
    "register_banner_defaults",
)


def _set_event_threadsafe(
    event: asyncio.Event,
    async_loop: asyncio.AbstractEventLoop | None,
    lifecycle_logger: LoggerProtocol,
) -> None:
    if async_loop and (not async_loop.is_closed()):
        try:
            async_loop.call_soon_threadsafe(event.set)
            return
        except RuntimeError as exception:
            lifecycle_logger.debug(
                "Lifecycle event loop closed while scheduling signal; setting event directly: %s",
                str(exception),
            )
    event.set()


def initiate_restart_signal(
    system_stop_event: asyncio.Event,
    async_loop: asyncio.AbstractEventLoop | None,
    lifecycle_logger: LoggerProtocol,
    is_shutting_down: bool,
) -> bool:
    if is_shutting_down or system_stop_event.is_set():
        lifecycle_logger.warning("Shutdown or restart already in progress. Ignoring request.")
        return False
    lifecycle_logger.warning(
        "Restart initiated. Scheduling a graceful shutdown and in-process restart.",
    )
    _set_event_threadsafe(system_stop_event, async_loop, lifecycle_logger)
    return True


def request_runtime_restart(
    runtime: RuntimeStateStoreProtocol,
    lifecycle_logger: LoggerProtocol,
    reason: str = "",
) -> bool:
    normalized_reason = str(reason or "").strip()
    if normalized_reason:
        lifecycle_logger.info("System restart requested: %s", normalized_reason)
    requested = initiate_restart_signal(
        runtime.system_stop_event,
        runtime.async_loop,
        lifecycle_logger,
        runtime.is_shutting_down,
    )
    if requested:
        runtime.set_restart_required()
    return requested


def require_runtime_restart(
    runtime: RuntimeStateStoreProtocol,
    lifecycle_logger: LoggerProtocol,
    reason: str,
) -> bool:
    if request_runtime_restart(runtime, lifecycle_logger, reason):
        return True
    runtime.set_restart_required()
    lifecycle_logger.info("Restart requirement attached to the active shutdown.")
    return True


def initiate_shutdown_signal(
    shutdown_event: asyncio.Event,
    system_stop_event: asyncio.Event,
    async_loop: asyncio.AbstractEventLoop | None,
    reason: str | None,
    lifecycle_logger: LoggerProtocol,
    is_shutting_down: bool,
) -> bool:
    if is_shutting_down or shutdown_event.is_set() or system_stop_event.is_set():
        lifecycle_logger.warning("Shutdown already in progress. Ignoring request.")
        return False
    message = "Application shutdown initiated. Scheduling a graceful stop."
    if reason:
        trimmed = reason.strip()
        if trimmed:
            message = f"{message} Reason: {trimmed}"
    lifecycle_logger.warning(message)
    _set_event_threadsafe(system_stop_event, async_loop, lifecycle_logger)
    return True


def register_banner_defaults(
    banner_system: BannerSystemProtocol,
    log_banner_defaults: list[tuple[str, str, str, int]],
) -> None:
    for key, color, message, level in log_banner_defaults:
        if not banner_system.has_banner(key):
            banner_system.register(key=key, color=color, message=message, level=level)
