"""SoAI - Event bus config parsing helpers [backend/core/events/bus_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.config.protocols import ConfigValue
    from core.types.json import JSONDict

__all__ = ("parse_positive_config",)

OPERATION_CORE_EVENTS_BUS_CONFIG_PARSE_POSITIVE_CONFIG = (
    "core.events.bus_config.parse_positive_config"
)


def parse_positive_config[NumericT: (int, float)](
    *,
    value: ConfigValue | None,
    coercer: Callable[[ConfigValue], NumericT | None],
    logger: LoggerProtocol,
    message: str,
    operation: str,
    details: JSONDict,
    default: NumericT | None,
) -> NumericT | None:
    if not value:
        return default
    try:
        coerced = coercer(value)
        if coerced is None:
            return default
        if coerced > 0:
            return coerced
    except (TypeError, ValueError) as exception:
        merged_details = dict(details)
        merged_details["config_operation"] = operation
        log_exception(
            logger,
            exception,
            message=message,
            operation=OPERATION_CORE_EVENTS_BUS_CONFIG_PARSE_POSITIVE_CONFIG,
            details=merged_details,
            level="warning",
        )
    return default
