"""SoAI - Shared token throughput calculation [backend/core/openai/token_rate_calculation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

__all__ = (
    "TOKEN_RATE_SMOOTHING_TIME_CONSTANT_MS",
    "TOKEN_RATE_UPDATE_INTERVAL_MS",
    "calculate_smoothed_token_rate",
)

TOKEN_RATE_UPDATE_INTERVAL_MS = 250
TOKEN_RATE_SMOOTHING_TIME_CONSTANT_MS = 2_000


def calculate_smoothed_token_rate(
    *,
    previous_rate: float,
    token_delta: int,
    elapsed_ms: int,
) -> float:
    raw_rate = float(token_delta) * 1000.0 / float(elapsed_ms)
    if previous_rate <= 0.0:
        return raw_rate
    alpha = 1.0 - math.exp(
        -float(elapsed_ms) / float(TOKEN_RATE_SMOOTHING_TIME_CONSTANT_MS),
    )
    return previous_rate + alpha * (raw_rate - previous_rate)
