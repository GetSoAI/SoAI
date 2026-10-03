"""SoAI - Typed network policy and download errors [backend/core/network/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import ExternalServiceError

__all__ = (
    "HTTPDownloadInsecureSchemeError",
    "HTTPDownloadSizeLimitError",
    "HTTPDownloadRedirectError",
    "HTTPDownloadTooManyRedirectsError",
    "HTTPReadUnavailableError",
    "NetworkPolicyDeniedError",
    "NetworkPolicyError",
    "NetworkPolicyResolutionError",
)


class NetworkPolicyError(ValidationError): ...


class NetworkPolicyDeniedError(NetworkPolicyError): ...


class NetworkPolicyResolutionError(NetworkPolicyError): ...


class HTTPDownloadInsecureSchemeError(ValidationError): ...


class HTTPDownloadSizeLimitError(ValidationError): ...


class HTTPDownloadRedirectError(ValidationError): ...


class HTTPDownloadTooManyRedirectsError(HTTPDownloadRedirectError): ...


class HTTPReadUnavailableError(ExternalServiceError): ...
