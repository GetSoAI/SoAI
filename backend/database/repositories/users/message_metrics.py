"""SoAI - Message repository metrics helpers [backend/database/repositories/users/message_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("calculate_generation_speed_tokens_per_sec",)


def calculate_generation_speed_tokens_per_sec(
    completion_tokens: int | None,
    generation_latency_ms: int | None,
) -> float | None:
    if (
        completion_tokens is None
        or generation_latency_ms is None
        or completion_tokens <= 0
        or generation_latency_ms <= 0
    ):
        return None
    return round((completion_tokens / generation_latency_ms) * 1000, 2)
