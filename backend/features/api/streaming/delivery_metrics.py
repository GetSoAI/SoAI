"""SoAI - Streaming delivery metric helpers [backend/features/api/streaming/delivery_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = ("record_delivery_metric",)


def record_delivery_metric(
    metrics_manager: MetricsManagerProtocol | None,
    key: tuple[str, ...],
    value: int = 1,
) -> None:
    if metrics_manager is not None:
        metrics_manager.increment_counter(*key, value=value)
