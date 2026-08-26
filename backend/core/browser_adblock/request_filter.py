"""SoAI - Shared request filtering decisions for adblock routing [backend/core/browser_adblock/request_filter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol

__all__ = (
    "RequestFilterDecision",
    "evaluate_request_filter",
    "normalize_request_type",
    "resolve_document_host",
)

COMMON_TWO_LABEL_PUBLIC_SUFFIXES = frozenset(
    {
        "co.uk",
        "com.au",
        "com.br",
        "com.cn",
        "com.mx",
        "com.tr",
        "co.jp",
        "co.kr",
        "co.nz",
        "co.in",
        "org.uk",
        "net.au",
    },
)


@dataclass(frozen=True, slots=True)
class RequestFilterDecision:
    block: bool


def evaluate_request_filter(
    *,
    request_url: str,
    resource_type: str,
    is_main_frame_document: bool | None,
    frame_url: str | None,
    referer: str | None,
    block_images: bool,
    block_fonts: bool,
    block_media: bool,
    block_ads: bool,
    adblock_service: EasyListAdblockServiceProtocol | None,
) -> RequestFilterDecision:
    normalized_resource_type = (resource_type or "").strip().lower()
    if block_images and normalized_resource_type == "image":
        return RequestFilterDecision(block=True)
    if block_fonts and normalized_resource_type == "font":
        return RequestFilterDecision(block=True)
    if block_media and normalized_resource_type == "media":
        return RequestFilterDecision(block=True)
    if not block_ads or adblock_service is None:
        return RequestFilterDecision(block=False)
    request_host = _extract_host(request_url)
    document_host = resolve_document_host(frame_url=frame_url, referer=referer)
    if request_host is None:
        return RequestFilterDecision(block=False)
    normalized_easylist_type = normalize_request_type(
        resource_type=normalized_resource_type,
        is_main_frame_document=is_main_frame_document,
        frame_url=frame_url,
    )
    is_third_party = _resolve_third_party(request_host=request_host, document_host=document_host)
    match_result = adblock_service.match(
        request_url,
        request_host=request_host,
        request_type=normalized_easylist_type,
        document_host=document_host,
        is_third_party=is_third_party,
    )
    if match_result.matched:
        return RequestFilterDecision(block=True)
    return RequestFilterDecision(block=False)


def normalize_request_type(
    *,
    resource_type: str,
    is_main_frame_document: bool | None,
    frame_url: str | None,
) -> str | None:
    if resource_type in {"xhr", "fetch", "eventsource"}:
        return "xmlhttprequest"
    if resource_type == "document":
        if is_main_frame_document is True:
            return "document"
        if is_main_frame_document is False:
            return "subdocument"
        if frame_url is None:
            return "document"
        request_frame_url = frame_url.strip()
        return (
            "document"
            if not request_frame_url or request_frame_url == "about:blank"
            else "subdocument"
        )
    if resource_type in {"font", "image", "media", "script", "stylesheet"}:
        return resource_type
    return None


def resolve_document_host(*, frame_url: str | None, referer: str | None) -> str | None:
    frame_host = _extract_host(frame_url)
    if frame_host is not None:
        return frame_host
    return _extract_host(referer)


def _extract_host(url: str | None) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    host = (urlparse(url).hostname or "").strip().lower()
    return host or None


def _resolve_third_party(*, request_host: str, document_host: str | None) -> bool | None:
    if document_host is None:
        return None
    request_domain = _registrable_domain(request_host)
    document_domain = _registrable_domain(document_host)
    if request_domain is not None and document_domain is not None:
        return request_domain != document_domain
    if request_host == document_host:
        return False
    return True


def _registrable_domain(host: str) -> str | None:
    parts = [part for part in host.strip(".").lower().split(".") if part]
    if len(parts) < 2:
        return None
    suffix = ".".join(parts[-2:])
    if suffix in COMMON_TWO_LABEL_PUBLIC_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return suffix
