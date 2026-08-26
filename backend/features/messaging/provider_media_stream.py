"""SoAI - Authenticated bounded provider media streams [backend/features/messaging/provider_media_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx2

from core.errors.exceptions import SecurityError, ServiceUnavailableError, ValidationError
from core.network.http_download_metadata import read_http_download_response_metadata
from core.network.http_transport import build_pinned_host_extensions
from core.runtime.network_policy import validate_runtime_url
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("ProviderMediaStream", "open_provider_media_stream")

PROVIDER_MEDIA_TIMEOUT_SECONDS = 30.0


@dataclass(slots=True)
class ProviderMediaStream:
    response: httpx2.Response
    chunks: AsyncIterator[bytes]
    max_bytes: int
    declared_size: int | None
    content_type: str | None
    bytes_read: int = 0

    async def read_chunk(self, _maximum_bytes: int) -> bytes:
        try:
            chunk = await anext(self.chunks)
        except StopAsyncIteration:
            return b""
        except httpx2.TimeoutException as exception:
            raise ServiceUnavailableError("Messaging provider media read timed out.") from exception
        except httpx2.RequestError as exception:
            raise ServiceUnavailableError("Messaging provider media stream failed.") from exception
        self.bytes_read += len(chunk)
        if self.bytes_read > self.max_bytes:
            raise ValidationError("Messaging provider media exceeds the configured file limit.")
        return chunk

    async def close(self) -> None:
        await self.response.aclose()


def _require_allowed_provider_url(url: str, allowed_host_suffixes: tuple[str, ...]) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not any(
            hostname == suffix or hostname.endswith(f".{suffix}")
            for suffix in allowed_host_suffixes
        )
    ):
        raise SecurityError("Messaging provider media URL is not an approved endpoint.")
    return url


async def open_provider_media_stream(
    *,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    url: str,
    allowed_host_suffixes: tuple[str, ...],
    headers: dict[str, str] | None,
    max_bytes: int,
) -> ProviderMediaStream:
    validated_url = _require_allowed_provider_url(url, allowed_host_suffixes)
    parsed = urlsplit(validated_url)
    pinned_host = await validate_runtime_url(
        runtime_flags,
        validated_url,
        source="Messaging provider media",
    )
    extensions = (
        build_pinned_host_extensions(pinned_host, parsed.hostname or "")
        if pinned_host is not None
        else None
    )
    request = http_client.build_request(
        "GET",
        validated_url,
        headers=headers,
        timeout=PROVIDER_MEDIA_TIMEOUT_SECONDS,
        extensions=extensions,
    )
    try:
        response = await asyncio.wait_for(
            http_client.send(request, stream=True, follow_redirects=False),
            timeout=PROVIDER_MEDIA_TIMEOUT_SECONDS,
        )
    except (TimeoutError, httpx2.TimeoutException) as exception:
        raise ServiceUnavailableError("Messaging provider media request timed out.") from exception
    except httpx2.RequestError as exception:
        raise ServiceUnavailableError("Messaging provider media request failed.") from exception
    if response.status_code in (301, 302, 303, 307, 308):
        await response.aclose()
        raise SecurityError("Messaging provider media redirects are not allowed.")
    if response.status_code in (429, 500, 502, 503, 504):
        await response.aclose()
        raise ServiceUnavailableError("Messaging provider media is temporarily unavailable.")
    if response.status_code < 200 or response.status_code >= 300:
        await response.aclose()
        raise ValidationError("Messaging provider rejected the media request.")
    try:
        metadata = read_http_download_response_metadata(response.headers, max_bytes=max_bytes)
    except ValidationError:
        await response.aclose()
        raise
    return ProviderMediaStream(
        response=response,
        chunks=response.aiter_bytes(),
        max_bytes=max_bytes,
        declared_size=metadata.declared_content_length,
        content_type=metadata.content_type,
    )
