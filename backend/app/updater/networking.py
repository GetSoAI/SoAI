"""SoAI - Updater HTTP request validation and streaming open helpers [backend/app/updater/networking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ssl
from collections.abc import Generator
from contextlib import contextmanager
from urllib import request
from urllib.parse import urljoin, urlsplit

import httpx2

from core.errors.exceptions import ValidationError
from core.network.outbound_http_profiles import (
    build_artifact_download_headers,
    build_outbound_request_headers,
    merge_outbound_headers,
)
from core.network.policy import enforce_url_local_only_policy_sync
from core.network.urls import replace_url_host, require_absolute_http_url

__all__ = (
    "open_url",
    "validate_updater_url",
)


def validate_updater_url(url: str) -> str:
    try:
        return require_absolute_http_url(url)
    except ValidationError as exception:
        raise ValidationError(str(exception), details={"url": url}) from exception


def _require_https_response(response: httpx2.Response) -> None:
    response_url = str(response.request.url)
    if urlsplit(response_url).scheme.lower() != "https":
        raise ValidationError(
            "Updater response URL must use https scheme.",
            details={"url": response_url},
        )
    if not response.is_redirect:
        return
    redirect_location = response.headers.get("Location")
    if redirect_location is None:
        return
    redirect_url = urljoin(response_url, redirect_location)
    if urlsplit(redirect_url).scheme.lower() != "https":
        raise ValidationError(
            "Updater redirect must use https scheme.",
            details={"url": redirect_url},
        )


@contextmanager
def open_url(
    target: str | request.Request,
    *,
    timeout: float,
    context: ssl.SSLContext | None = None,
    stream: bool = False,
    require_https: bool = False,
    offline_mode: bool,
    default_headers: dict[str, str] | None = None,
    artifact_download: bool = False,
) -> Generator[httpx2.Response]:
    url = ""
    method = "GET"
    headers: dict[str, str] | None = None
    content: bytes | None = None
    if isinstance(target, request.Request):
        try:
            url = str(target.full_url or "")
        except AttributeError:
            url = ""
        method = str(target.get_method() or "GET").upper()
        try:
            raw_headers = target.headers
        except AttributeError:
            raw_headers = None
        if isinstance(raw_headers, dict):
            headers = {
                str(header_key): str(header_value)
                for header_key, header_value in raw_headers.items()
            }
        try:
            raw_data = target.data
        except AttributeError:
            raw_data = None
        if isinstance(raw_data, bytes):
            content = raw_data
        elif isinstance(raw_data, str):
            content = raw_data.encode("utf-8")
    else:
        url = str(target or "")
    if artifact_download:
        stream = True
        require_https = True
        offline_mode = False
        default_headers = build_artifact_download_headers()
    validated = validate_updater_url(url)
    if require_https and urlsplit(validated).scheme.lower() != "https":
        raise ValidationError("Updater URL must use https scheme.", details={"url": validated})
    if offline_mode:
        pinned_host = enforce_url_local_only_policy_sync(
            validated,
            source="application updater",
        )
        if pinned_host:
            validated = replace_url_host(validated, pinned_host)
    client = httpx2.Client(
        headers=(
            default_headers
            if default_headers is not None
            else build_outbound_request_headers(profile_type="service_api")
        ),
        verify=context if context is not None else True,
        timeout=float(timeout),
        follow_redirects=not offline_mode,
        trust_env=not offline_mode,
        event_hooks={"response": [_require_https_response]} if require_https else None,
    )
    try:
        effective_headers = merge_outbound_headers({}, headers)
        if stream:
            with client.stream(
                method, validated, headers=effective_headers, content=content
            ) as response:
                yield response
        else:
            response = client.request(method, validated, headers=effective_headers, content=content)
            try:
                yield response
            finally:
                response.close()
    finally:
        client.close()
