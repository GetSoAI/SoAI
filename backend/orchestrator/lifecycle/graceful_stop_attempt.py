"""SoAI - Shared graceful plugin stop attempt logic [backend/orchestrator/lifecycle/graceful_stop_attempt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.plugins.protocols_instance import PluginInstanceProtocol

__all__ = (
    "GracefulStopAttempt",
    "attempt_graceful_plugin_stop",
)

OPERATION = "orchestrator.lifecycle.graceful_stop_attempt"


@dataclass(frozen=True, slots=True)
class GracefulStopAttempt:
    succeeded: bool
    timed_out: bool
    error_message: str | None
    exception: BaseException | None


async def attempt_graceful_plugin_stop(
    plugin_instance: PluginInstanceProtocol,
    *,
    plugin_name: str,
    graceful_budget_sec: float,
    logger: LoggerProtocol,
) -> GracefulStopAttempt:
    logger.debug(
        "Attempting graceful stop for '%s' with a %.3fs timeout.",
        plugin_name,
        graceful_budget_sec,
    )
    try:
        stop_result = await asyncio.wait_for(
            plugin_instance.stop(),
            timeout=graceful_budget_sec if graceful_budget_sec > 0 else 0.0,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Graceful plugin stop attempt failed.",
            operation=OPERATION,
            details={
                "plugin_name": plugin_name,
                "graceful_budget_sec": graceful_budget_sec,
            },
            level="warning",
        )
        timed_out = isinstance(exception, asyncio.TimeoutError)
        stop_error_message = (
            f"Timed out after {graceful_budget_sec:.3f}s"
            if timed_out
            else project_public_exception(exception).message
        )
        return GracefulStopAttempt(
            succeeded=False,
            timed_out=timed_out,
            error_message=stop_error_message,
            exception=exception,
        )
    if not stop_result:
        stop_error_message = "Plugin stop returned unsuccessful result."
        logger.warning(
            "%s Plugin '%s' did not stop gracefully.",
            stop_error_message,
            plugin_name,
        )
        return GracefulStopAttempt(
            succeeded=False,
            timed_out=False,
            error_message=stop_error_message,
            exception=None,
        )
    logger.info("Plugin '%s' stopped gracefully.", plugin_name)
    return GracefulStopAttempt(
        succeeded=True,
        timed_out=False,
        error_message=None,
        exception=None,
    )
