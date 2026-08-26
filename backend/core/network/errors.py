"""SoAI - Typed network policy and download errors [backend/core/network/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "HTTPDownloadInsecureSchemeError",
    "HTTPDownloadRedirectError",
    "HTTPDownloadTooManyRedirectsError",
    "NetworkPolicyDeniedError",
    "NetworkPolicyError",
    "NetworkPolicyResolutionError",
)


class NetworkPolicyError(ValidationError): ...


class NetworkPolicyDeniedError(NetworkPolicyError): ...


class NetworkPolicyResolutionError(NetworkPolicyError): ...


class HTTPDownloadInsecureSchemeError(ValidationError): ...


class HTTPDownloadRedirectError(ValidationError): ...


class HTTPDownloadTooManyRedirectsError(HTTPDownloadRedirectError): ...
