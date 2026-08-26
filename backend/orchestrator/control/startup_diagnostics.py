"""SoAI - Orchestrator startup diagnostics logging [backend/orchestrator/control/startup_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.seconds_coercion import (
    coerce_timeout_log_value,
    format_timeout_seconds,
)
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("log_startup_configuration",)


def log_startup_configuration(
    *,
    logger: LoggerProtocol,
    health_check_config: JSONDict,
    max_concurrent_plugins: int,
    num_planner_workers: int,
) -> None:
    timeouts_value = health_check_config.get("COMMAND_TIMEOUTS_SEC")
    if timeouts_value is None:
        timeouts: JSONDict = {}
    elif is_json_dict(timeouts_value):
        timeouts = timeouts_value
    else:
        raise ValidationError("COMMAND_TIMEOUTS_SEC must be a JSON object.")
    plugin_load_timeout = coerce_timeout_log_value(timeouts.get("PLUGIN_LOAD_MODEL"))
    non_streaming_timeout = coerce_timeout_log_value(
        health_check_config.get("NON_STREAMING_TIMEOUT_SEC"),
    )
    stuck_state_timeout = coerce_timeout_log_value(
        health_check_config.get("STUCK_STATE_TIMEOUT_SEC"),
    )
    logger.debug(
        "Key timeouts: Load=%s, Request=%s, Stuck=%s",
        format_timeout_seconds(plugin_load_timeout),
        format_timeout_seconds(non_streaming_timeout),
        format_timeout_seconds(stuck_state_timeout),
    )
    logger.debug(
        "Orchestrator started with MAX_CONCURRENT_PLUGINS=%s and %s planner workers.",
        max_concurrent_plugins,
        num_planner_workers,
    )
