"""SoAI - Bounded remote fetch helpers for media previews [backend/webui/manager/media_preview_fetcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx2

from core.errors.exceptions import NotFoundError, ValidationError
from core.files.content_types import (
    content_type_is_html,
    content_type_is_text,
    normalize_content_type,
)
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.http_block_detection import (
    BlockedHTTPResponse,
    detect_blocked_http_response,
)
from core.network.http_transport import build_pinned_host_extensions
from core.network.outbound_http_profiles import (
    DEFAULT_BROWSER_ACCEPT_LANGUAGE,
    DEFAULT_BROWSER_DOCUMENT_USER_AGENTS,
    build_browser_document_headers,
)
from core.network.urls import normalize_http_url
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "BoundedFetchResult",
    "BoundedMediaFetcher",
)


@dataclass(frozen=True, slots=True)
class BoundedFetchResult:
    final_url: str
    status_code: int
    content_type: str
    payload_bytes: bytes
    blocked_response: BlockedHTTPResponse | None


class BoundedMediaFetcher:
    __slots__ = ("_browser_user_agents", "_policy", "_settings")

    def __init__(self, settings: MediaPreviewSettings, policy: RemoteMediaPolicy) -> None:
        self._browser_user_agents = DEFAULT_BROWSER_DOCUMENT_USER_AGENTS[:2]
        self._settings = settings
        self._policy = policy

    async def fetch_bytes_bounded(
        self,
        http_client: httpx2.AsyncClient,
        url: str,
        runtime_flags: RuntimeFlagsViewProtocol,
        *,
        max_bytes: int,
        timeout: float,
        headers: dict[str, str],
        source: str,
    ) -> BoundedFetchResult:
        request_profiles = self._build_request_profiles(headers)
        blocked_result: BoundedFetchResult | None = None
        for request_headers in request_profiles:
            result = await self._fetch_with_headers(
                http_client=http_client,
                url=url,
                runtime_flags=runtime_flags,
                max_bytes=max_bytes,
                timeout=timeout,
                headers=request_headers,
                source=source,
            )
            if result.blocked_response is None:
                return result
            blocked_result = result
        if blocked_result is not None:
            return blocked_result
        raise ValidationError("No browser request profiles were available.")

    def _build_request_profiles(self, headers: dict[str, str]) -> tuple[dict[str, str], ...]:
        accept = self._resolve_header_value(headers, "Accept", default_value="*/*")
        accept_language = self._resolve_header_value(
            headers,
            "Accept-Language",
            default_value=DEFAULT_BROWSER_ACCEPT_LANGUAGE,
        )
        profiles: list[dict[str, str]] = []
        for user_agent in self._browser_user_agents:
            profile = build_browser_document_headers(
                user_agent=user_agent,
                accept=accept,
                accept_language=accept_language,
            )
            self._merge_request_headers(profile=profile, request_headers=headers)
            profiles.append(profile)
        return tuple(profiles)

    async def _fetch_with_headers(
        self,
        *,
        http_client: httpx2.AsyncClient,
        url: str,
        runtime_flags: RuntimeFlagsViewProtocol,
        max_bytes: int,
        timeout: float,
        headers: dict[str, str],
        source: str,
    ) -> BoundedFetchResult:
        current = url
        redirected = False
        for _ in range(self._settings.max_redirects + 1):
            pinned_host = await self._policy.enforce(runtime_flags, current, source=source)
            request_extensions: dict[str, str] | None = None
            if pinned_host:
                original_host = urlparse(current).hostname
                if not original_host:
                    raise ValidationError("URL must include a hostname.")
                request_extensions = build_pinned_host_extensions(pinned_host, original_host)
            async with http_client.stream(
                "GET",
                current,
                headers=headers,
                follow_redirects=False,
                timeout=timeout,
                extensions=request_extensions,
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_location = response.headers.get("Location")
                    if not redirect_location:
                        raise ValidationError("Redirect response missing Location header.")
                    current = normalize_http_url(urljoin(current, redirect_location))
                    redirected = True
                    continue
                content_type = str(response.headers.get("Content-Type") or "").strip()
                payload_bytes = await self._read_payload(response=response, max_bytes=max_bytes)
                if response.status_code in (404, 410):
                    raise NotFoundError(
                        f"Remote preview URL responded with status {response.status_code}.",
                    )
                blocked_response = self._detect_blocked_response(
                    status_code=int(response.status_code),
                    url=current,
                    redirected=redirected,
                    content_type=content_type,
                    payload_bytes=payload_bytes,
                )
                if blocked_response is None and response.status_code >= 400:
                    raise ValidationError(f"Upstream responded with status {response.status_code}.")
                return BoundedFetchResult(
                    final_url=current,
                    status_code=int(response.status_code),
                    content_type=content_type,
                    payload_bytes=payload_bytes,
                    blocked_response=blocked_response,
                )
        raise ValidationError(f"Too many redirects (>{self._settings.max_redirects}).")

    async def _read_payload(self, *, response: httpx2.Response, max_bytes: int) -> bytes:
        total = 0
        chunks: list[bytes] = []
        async for chunk in response.aiter_bytes():
            if not chunk:
                continue
            remaining = max_bytes - total
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunks.append(chunk[:remaining])
                total = max_bytes
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)

    def _detect_blocked_response(
        self,
        *,
        status_code: int,
        url: str,
        redirected: bool,
        content_type: str,
        payload_bytes: bytes,
    ) -> BlockedHTTPResponse | None:
        body_text = None
        normalized_content_type = normalize_content_type(content_type)
        if (
            content_type_is_text(normalized_content_type)
            or content_type_is_html(normalized_content_type)
            or not normalized_content_type
        ):
            body_text = payload_bytes[:32768].decode("utf-8", errors="replace")
        return detect_blocked_http_response(
            status_code=status_code,
            url=url,
            redirected=redirected,
            body_text=body_text,
        )

    def _resolve_header_value(
        self,
        headers: dict[str, str],
        header_name: str,
        *,
        default_value: str,
    ) -> str:
        target_name = header_name.lower()
        for key, value in headers.items():
            if key.lower() != target_name:
                continue
            normalized_value = str(value).strip()
            if normalized_value:
                return normalized_value
            break
        return default_value

    def _merge_request_headers(
        self,
        *,
        profile: dict[str, str],
        request_headers: dict[str, str],
    ) -> None:
        profile_header_names = {key.lower() for key in profile}
        for key, value in request_headers.items():
            if key.lower() in profile_header_names:
                continue
            profile[key] = value
