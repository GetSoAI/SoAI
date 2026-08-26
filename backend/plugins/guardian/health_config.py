"""SoAI - Guardian health-check configuration parsing [backend/plugins/guardian/health_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.types.json import JSONDict

__all__ = (
    "GuardianHealthCheckConfig",
    "resolve_guardian_health_check_config",
)


@dataclass(frozen=True, slots=True)
class GuardianHealthCheckConfig:
    interval: float
    jitter: float
    streaming_idle_timeout: float
    non_streaming_timeout: float
    ping_timeout: float
    stuck_state_timeout: float
    idle_ping_grace_period: float
    flapping_window: float
    flapping_min_transitions: int


def resolve_guardian_health_check_config(config: JSONDict) -> GuardianHealthCheckConfig:
    return GuardianHealthCheckConfig(
        interval=coerce_positive_float(
            config.get("INTERVAL_SEC", 20.0),
            default=20.0,
            minimum=1.0,
        ),
        jitter=coerce_positive_float(
            config.get("JITTER_FRACTION", 0.1),
            default=0.1,
            minimum=0.0,
        ),
        streaming_idle_timeout=coerce_positive_float(
            config.get("STREAMING_IDLE_TIMEOUT_SEC", LONG_REQUEST_TIMEOUT_SEC),
            default=LONG_REQUEST_TIMEOUT_SEC,
            minimum=1.0,
        ),
        non_streaming_timeout=coerce_positive_float(
            config.get("NON_STREAMING_TIMEOUT_SEC", LONG_REQUEST_TIMEOUT_SEC),
            default=LONG_REQUEST_TIMEOUT_SEC,
            minimum=1.0,
        ),
        ping_timeout=coerce_positive_float(
            config.get("PING_TIMEOUT_SEC", 15.0),
            default=15.0,
            minimum=0.0,
        ),
        stuck_state_timeout=coerce_positive_float(
            config.get("STUCK_STATE_TIMEOUT_SEC", 900.0),
            default=900.0,
            minimum=0.0,
        ),
        idle_ping_grace_period=coerce_positive_float(
            config.get("IDLE_PING_GRACE_PERIOD_SEC", 5.0),
            default=5.0,
            minimum=0.0,
        ),
        flapping_window=coerce_positive_float(
            config.get("FLAPPING_WINDOW_SEC", 120.0),
            default=120.0,
            minimum=1.0,
        ),
        flapping_min_transitions=coerce_positive_int(
            config.get("FLAPPING_MIN_TRANSITIONS", 3),
            default=3,
            minimum=3,
            maximum=128,
        ),
    )
