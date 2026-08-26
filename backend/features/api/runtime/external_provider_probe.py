"""SoAI - External provider probe primitives [backend/features/api/runtime/external_provider_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import FeatureDisabledError
from core.errors.http_status_classification import resolve_probe_status_for_http_status
from core.runtime.network_policy import OfflineModeError

if TYPE_CHECKING:
    from typing import Literal

__all__ = (
    "KNOWN_OPENAI_PROVIDER_ENDPOINT_SUFFIXES",
    "OPENAI_PROVIDER_ENDPOINTS_TO_PROBE",
    "classify_probe_status",
)

KNOWN_OPENAI_PROVIDER_ENDPOINT_SUFFIXES: tuple[str, ...] = (
    "/models",
    "/responses",
    "/chat/completions",
    "/completions",
    "/embeddings",
    "/images/generations",
    "/audio/speech",
    "/audio/transcriptions",
    "/audio/translations",
)

OPENAI_PROVIDER_ENDPOINTS_TO_PROBE: tuple[str, ...] = (
    "/responses",
    "/chat/completions",
    "/embeddings",
    "/images/generations",
    "/audio/speech",
    "/completions",
)


def classify_probe_status(
    http_status: int | None,
    *,
    exception: BaseException | None,
) -> Literal[
    "present",
    "missing",
    "auth_failed",
    "rate_limited",
    "server_error",
    "invalid_request",
    "network_error",
    "timeout",
]:
    if exception is not None:
        if isinstance(exception, httpx2.TimeoutException):
            return "timeout"
        if isinstance(exception, httpx2.RequestError):
            return "network_error"
        if isinstance(exception, OfflineModeError | FeatureDisabledError):
            return "network_error"
        return "network_error"
    if http_status is None:
        return "network_error"
    return resolve_probe_status_for_http_status(http_status)
