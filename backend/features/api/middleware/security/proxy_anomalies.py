"""SoAI - API security proxy header anomaly tracking [backend/features/api/middleware/security/proxy_anomalies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.logging.trace import get_logger
from core.runtime.proxy_headers import parse_forwarded_proto, parse_x_forwarded_proto
from core.runtime.state_access import read_request_state_flag, read_state_flag
from core.system_api.request_paths import get_scope_path
from core.timing.epoch import epoch_seconds
from core.validation.coercion import coerce_int_from_numberish
from features.api.middleware.security.types import ProxyHeaderAnomalyTracker
from features.api.runtime.app_state_access import require_app_state

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("record_proxy_header_anomaly",)

LOGGER_NAME = "SoAI.features.api.proxy_anomalies"


def record_proxy_header_anomaly(request: Request, tracker: ProxyHeaderAnomalyTracker) -> None:
    state = require_app_state(request)
    proxy_headers_enabled = read_state_flag(state, "proxy_headers_enabled")
    if proxy_headers_enabled:
        return
    if not _request_indicates_https_proxy(request):
        return
    proxy_alert_recorded = read_request_state_flag(request, "proxy_alert_recorded")
    if proxy_alert_recorded:
        return
    now = int(epoch_seconds())
    if not tracker.lock.acquire(blocking=False):
        return
    try:
        alert: JSONDict
        if isinstance(tracker.alert, dict):
            alert = tracker.alert
        else:
            alert = {"count": 0}
            tracker.alert = alert
        alert["count"] = _coerce_alert_count(alert.get("count")) + 1
        if "first_seen" not in alert:
            alert["first_seen"] = now
        alert["last_seen"] = now
        alert["last_path"] = get_scope_path(request.scope)
        client = request.client
        alert["last_client"] = client.host if client else None
    finally:
        tracker.lock.release()
    request.state.proxy_alert_recorded = True
    if alert["count"] == 1:
        get_logger(LOGGER_NAME).warning(
            "HTTPS proxy headers were received while proxy support is disabled. Configure SERVER.HTTP.PROXY.TRUSTED_NETWORKS or disable REQUIRE_SECURE_TRANSPORT.",
        )


def _request_indicates_https_proxy(request: Request) -> bool:
    forwarded_proto = parse_x_forwarded_proto(request.headers.get("x-forwarded-proto"))
    if forwarded_proto == "https":
        return True
    structured = parse_forwarded_proto(request.headers.get("forwarded"))
    return structured == "https"


def _coerce_alert_count(value: JSONValue) -> int:
    return coerce_int_from_numberish(value) or 0
