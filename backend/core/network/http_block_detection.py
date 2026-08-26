"""SoAI - Shared HTTP blocked/interstitial response detection [backend/core/network/http_block_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

__all__ = (
    "BlockedHTTPResponse",
    "detect_blocked_http_response",
)


@dataclass(frozen=True, slots=True)
class BlockedHTTPResponse:
    reason: str
    match: str
    value: str | int
    url: str
    redirected: bool
    snippet: str | None


def detect_blocked_http_response(
    *,
    status_code: int,
    url: str,
    redirected: bool,
    body_text: str | None,
) -> BlockedHTTPResponse | None:
    url_block = _detect_url_block(url=url, redirected=redirected)
    if url_block is not None:
        return url_block
    if body_text is None:
        return _detect_status_code_block(status_code=status_code, url=url, redirected=redirected)
    lowered_body = body_text.lower()
    if _contains_recaptcha_challenge(lowered_body):
        return _build_blocked_response(
            reason="captcha_page",
            match="body",
            value="recaptcha",
            url=url,
            redirected=redirected,
            snippet=_first_matching_snippet(
                text=body_text,
                needles=(
                    "g-recaptcha",
                    "grecaptcha.render",
                    "recaptcha/api.js",
                    'class="h-captcha"',
                    "hcaptcha.com/1/api.js",
                ),
            ),
        )
    if _contains_turnstile_challenge(lowered_body):
        return _build_blocked_response(
            reason="turnstile_challenge",
            match="body",
            value="turnstile",
            url=url,
            redirected=redirected,
            snippet=_first_matching_snippet(
                text=body_text,
                needles=("cf-turnstile", "challenges.cloudflare.com/turnstile", "turnstile.render"),
            ),
        )
    if _contains_cloudflare_attention_challenge(lowered_body):
        return _build_blocked_response(
            reason="cloudflare_challenge",
            match="body",
            value="cloudflare_attention_required",
            url=url,
            redirected=redirected,
            snippet=_first_snippet(body_text, needle="attention required"),
        )
    if "cf-chl" in lowered_body:
        return _build_blocked_response(
            reason="cloudflare_challenge",
            match="body",
            value="cf_chl",
            url=url,
            redirected=redirected,
            snippet=_first_snippet(body_text, needle="cf-chl"),
        )
    if _contains_cloudflare_waiting_room(lowered_body):
        return _build_blocked_response(
            reason="cloudflare_challenge",
            match="body",
            value="just_a_moment",
            url=url,
            redirected=redirected,
            snippet=_first_snippet(body_text, needle="just a moment"),
        )
    if _contains_bot_interstitial(lowered_body):
        return _build_blocked_response(
            reason="bot_interstitial",
            match="body",
            value="unusual_traffic",
            url=url,
            redirected=redirected,
            snippet=_first_matching_snippet(
                text=body_text,
                needles=("automated queries", "unusual traffic from your computer network"),
            ),
        )
    return _detect_status_code_block(status_code=status_code, url=url, redirected=redirected)


def _detect_status_code_block(
    *,
    status_code: int,
    url: str,
    redirected: bool,
) -> BlockedHTTPResponse | None:
    if status_code == 401:
        return _build_blocked_response(
            reason="auth_required",
            match="status_code",
            value=401,
            url=url,
            redirected=redirected,
            snippet=None,
        )
    if status_code in (500, 502, 503, 504):
        return _build_blocked_response(
            reason="upstream_unavailable",
            match="status_code",
            value=status_code,
            url=url,
            redirected=redirected,
            snippet=None,
        )
    if status_code == 429:
        return _build_blocked_response(
            reason="rate_limited",
            match="status_code",
            value=429,
            url=url,
            redirected=redirected,
            snippet=None,
        )
    if status_code == 403:
        return _build_blocked_response(
            reason="forbidden",
            match="status_code",
            value=403,
            url=url,
            redirected=redirected,
            snippet=None,
        )
    return None


def _detect_url_block(*, url: str, redirected: bool) -> BlockedHTTPResponse | None:
    lowered_url = str(url or "").strip().lower()
    if not lowered_url:
        return None
    parsed_url = urlparse(lowered_url)
    hostname = (parsed_url.hostname or "").strip().lower()
    path = (parsed_url.path or "").strip().lower()
    if hostname.endswith("google.com") and path.startswith("/sorry"):
        return _build_blocked_response(
            reason="captcha_interstitial",
            match="url",
            value=url,
            url=url,
            redirected=redirected,
            snippet=None,
        )
    return None


def _build_blocked_response(
    *,
    reason: str,
    match: str,
    value: str | int,
    url: str,
    redirected: bool,
    snippet: str | None,
) -> BlockedHTTPResponse:
    return BlockedHTTPResponse(
        reason=reason,
        match=match,
        value=value,
        url=url,
        redirected=redirected,
        snippet=snippet,
    )


def _first_snippet(text: str, *, needle: str) -> str:
    lowered = text.lower()
    index = lowered.find(needle.lower())
    if index < 0:
        return text[:200]
    start = max(0, index - 60)
    end = min(len(text), index + 140)
    return text[start:end].strip()


def _first_matching_snippet(text: str, *, needles: tuple[str, ...]) -> str:
    lowered = text.lower()
    for needle in needles:
        if needle.lower() in lowered:
            return _first_snippet(text, needle=needle)
    return text[:200]


def _contains_recaptcha_challenge(lowered_body: str) -> bool:
    return (
        ("g-recaptcha" in lowered_body and "data-sitekey" in lowered_body)
        or "grecaptcha.render" in lowered_body
        or ("recaptcha/api.js" in lowered_body and "data-sitekey" in lowered_body)
        or 'class="h-captcha"' in lowered_body
        or ("hcaptcha.com/1/api.js" in lowered_body and "data-sitekey" in lowered_body)
    )


def _contains_turnstile_challenge(lowered_body: str) -> bool:
    return (
        "cf-turnstile" in lowered_body
        or "challenges.cloudflare.com/turnstile" in lowered_body
        or "turnstile.render" in lowered_body
    )


def _contains_cloudflare_attention_challenge(lowered_body: str) -> bool:
    return "cloudflare" in lowered_body and "attention required" in lowered_body


def _contains_cloudflare_waiting_room(lowered_body: str) -> bool:
    if "just a moment" not in lowered_body:
        return False
    return (
        "cloudflare" in lowered_body
        or "checking your browser" in lowered_body
        or "enable javascript and cookies" in lowered_body
    )


def _contains_bot_interstitial(lowered_body: str) -> bool:
    return (
        "automated queries" in lowered_body
        or "unusual traffic from your computer network" in lowered_body
    )
