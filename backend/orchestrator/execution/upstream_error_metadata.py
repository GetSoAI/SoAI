"""SoAI - Upstream provider error metadata parsing [backend/orchestrator/execution/upstream_error_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import IpcRemoteRequestError
from core.errors.external_service_exception import ExternalServiceError
from core.validation.integers import is_strict_int

__all__ = (
    "has_upstream_provider_marker",
    "is_upstream_transport_error",
    "resolve_upstream_http_status",
    "resolve_upstream_retry_after",
)


def resolve_upstream_http_status(
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> int | None:
    status_value = exception.details.get("upstream_http_status") if exception.details else None
    if not is_strict_int(status_value):
        return None
    if status_value <= 0:
        return None
    return status_value


def resolve_upstream_retry_after(
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> str | None:
    retry_after_value = exception.details.get("upstream_retry_after") if exception.details else None
    if not isinstance(retry_after_value, str):
        return None
    normalized = retry_after_value.strip()
    return normalized or None


def has_upstream_provider_marker(
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> bool:
    provider_value = exception.details.get("upstream_provider") if exception.details else None
    return isinstance(provider_value, str) and bool(provider_value.strip())


def is_upstream_transport_error(
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> bool:
    transport_value = (
        exception.details.get("upstream_transport_error") if exception.details else None
    )
    return transport_value is True
