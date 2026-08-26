"""SoAI - Browser navigation block detection [backend/mcp/tools/browser/navigation_block_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

from core.network.http_block_detection import (
    BlockedHTTPResponse,
    detect_blocked_http_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.browser.types import BrowserNetworkRequest, BrowserSessionState

__all__ = ("apply_navigation_block_detection",)


def apply_navigation_block_detection(
    result: JSONDict,
    state: BrowserSessionState,
) -> None:
    final_url = str(result.get("url") or "")
    blocked = _detect_final_url_block(final_url)
    if blocked is None:
        blocked = _detect_current_navigation_document_block(state, final_url=final_url)
    if blocked is None:
        result["blocked"] = False
        return
    result["blocked"] = True
    result["blocked_reason"] = blocked.reason
    result["blocked_evidence"] = _blocked_evidence(blocked)
    result["recovery_hints"] = _recovery_hints(blocked)


def _detect_final_url_block(url: str) -> BlockedHTTPResponse | None:
    if not url:
        return None
    return detect_blocked_http_response(
        status_code=200,
        url=url,
        redirected=False,
        body_text=None,
    )


def _detect_current_navigation_document_block(
    state: BrowserSessionState,
    *,
    final_url: str,
) -> BlockedHTTPResponse | None:
    start = max(0, int(state.network_page_load_index))
    current_requests = state.network_requests[start:]
    for request in reversed(current_requests):
        if not _is_top_level_document(request):
            continue
        if not _same_url_without_fragment(request.url, final_url):
            continue
        status = request.status
        if status is None:
            return None
        return detect_blocked_http_response(
            status_code=int(status),
            url=request.url,
            redirected=False,
            body_text=request.body,
        )
    return None


def _is_top_level_document(request: BrowserNetworkRequest) -> bool:
    resource_type = str(request.resource_type or "").strip().lower()
    return resource_type == "document" and request.is_main_frame_document is True


def _same_url_without_fragment(left: str, right: str) -> bool:
    return _url_without_fragment(left) == _url_without_fragment(right)


def _url_without_fragment(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return urlunparse(parsed._replace(fragment=""))


def _blocked_evidence(blocked: BlockedHTTPResponse) -> JSONDict:
    evidence: JSONDict = {
        "match": blocked.match,
        "value": blocked.value,
        "url": blocked.url,
        "redirected": blocked.redirected,
    }
    if blocked.snippet is not None:
        evidence["snippet"] = blocked.snippet
    return evidence


def _recovery_hints(blocked: BlockedHTTPResponse) -> list[JSONValue]:
    reason = blocked.reason
    if reason in {"captcha_page", "turnstile_challenge", "cloudflare_challenge"}:
        return [
            "Use a persistent user_data_dir or CDP profile with a real browser session.",
            "Complete any required verification manually in the headed browser, then retry.",
            "Avoid repeated retries from fresh empty browser sessions.",
        ]
    if reason == "rate_limited":
        return [
            "Wait before retrying.",
            "Use an existing persistent browser profile instead of a fresh session.",
        ]
    if reason == "auth_required":
        return [
            "Sign in with the same persistent browser profile or provide supported credentials.",
        ]
    if reason == "forbidden":
        return [
            "Use a persistent browser profile with normal logged-in state when access is allowed.",
        ]
    return [
        "Inspect browser_network and browser_console for details before retrying.",
    ]
