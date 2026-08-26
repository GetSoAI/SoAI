"""SoAI - Proxy header anomaly tracker operations [backend/features/api/middleware/security/anomaly_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.middleware.security.types import ProxyHeaderAnomalyTracker

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "reset_anomaly_alert",
    "snapshot_anomaly_alert",
)


def snapshot_anomaly_alert(tracker: ProxyHeaderAnomalyTracker) -> JSONDict | None:
    with tracker.lock:
        return dict(tracker.alert) if isinstance(tracker.alert, dict) else None


def reset_anomaly_alert(tracker: ProxyHeaderAnomalyTracker) -> None:
    with tracker.lock:
        tracker.alert = None
