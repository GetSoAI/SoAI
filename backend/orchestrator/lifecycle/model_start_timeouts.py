"""SoAI - Orchestrator model start timeout policy helpers [backend/orchestrator/lifecycle/model_start_timeouts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.timing.constants import CONTROL_TIMEOUT_SEC

__all__ = ("resolve_start_with_model_timeout",)

_START_WITH_MODEL_TIMEOUT_FRACTION: float = 0.25
_START_WITH_MODEL_TIMEOUT_CAP_SEC: float = 900.0


def resolve_start_with_model_timeout(load_timeout_sec: float) -> float:
    return min(
        load_timeout_sec,
        max(
            CONTROL_TIMEOUT_SEC,
            min(
                load_timeout_sec * _START_WITH_MODEL_TIMEOUT_FRACTION,
                _START_WITH_MODEL_TIMEOUT_CAP_SEC,
            ),
        ),
    )
