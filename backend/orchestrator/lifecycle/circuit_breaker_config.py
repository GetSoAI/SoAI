"""SoAI - Circuit breaker config resolution [backend/orchestrator/lifecycle/circuit_breaker_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.logging.trace import get_logger
from orchestrator.lifecycle.circuit_breaker_types import CircuitBreakerConfigDict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_circuit_breaker_config",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.circuit_breaker_config"


def build_circuit_breaker_config(health_check_config: JSONValue) -> CircuitBreakerConfigDict:
    logger = get_logger(LOGGER_NAME)
    health_check_map = dict(health_check_config) if isinstance(health_check_config, dict) else {}
    failure_threshold = coerce_positive_int(
        health_check_map.get("FAILURE_THRESHOLD", 3),
        default=3,
        minimum=1,
        label="MODELS.ROUTING.HEALTH_CHECKS.FAILURE_THRESHOLD",
        logger=logger,
    )
    recovery_timeout = coerce_positive_float(
        health_check_map.get("RECOVERY_TIMEOUT_SEC", 1440.0),
        default=1440.0,
        minimum=0.0,
        label="MODELS.ROUTING.HEALTH_CHECKS.RECOVERY_TIMEOUT_SEC",
        logger=logger,
    )
    failure_window = coerce_positive_float(
        health_check_map.get("FAILURE_WINDOW_SEC", recovery_timeout),
        default=recovery_timeout,
        minimum=0.0,
        label="MODELS.ROUTING.HEALTH_CHECKS.FAILURE_WINDOW_SEC",
        logger=logger,
    )
    return {
        "failure_threshold": failure_threshold,
        "recovery_timeout_sec": recovery_timeout,
        "failure_window_sec": failure_window,
    }
