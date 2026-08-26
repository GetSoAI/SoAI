"""SoAI - MCP web scraper URL validation and network policy [backend/mcp/rag/scraper/url_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import ParseResult, parse_qsl, urlencode, urlparse, urlunparse

from core.network.policy import enforce_url_network_policy
from core.network.urls import normalize_http_url
from core.runtime.network_policy import is_offline_mode_enabled, validate_local_only_url
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "canonicalize_fetch_cache_url",
    "generate_url_variants",
    "normalize_http_url",
    "validate_fetch_url",
)

_TRACKING_QUERY_PREFIXES: tuple[str, ...] = ("utm_",)
_TRACKING_QUERY_KEYS: frozenset[str] = frozenset(("gclid", "fbclid", "mc_cid", "mc_eid", "ref"))


def canonicalize_fetch_cache_url(url: str) -> str:
    normalized_url = normalize_http_url(url)
    parsed = urlparse(normalized_url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in query_pairs:
        key_lower = key.lower()
        if key_lower.startswith(_TRACKING_QUERY_PREFIXES):
            continue
        if key_lower in _TRACKING_QUERY_KEYS:
            continue
        filtered_pairs.append((key, value))
    filtered_pairs.sort(key=lambda item: (item[0], item[1]))
    canonical_query = urlencode(filtered_pairs, doseq=True)
    canonical_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            canonical_query,
            "",
        ),
    )
    return canonical_url


def generate_url_variants(
    url: str,
    *,
    include_http_fallback_for_https: bool = True,
) -> list[str]:
    normalized_url = (url or "").strip()
    parsed: ParseResult = urlparse(normalized_url)
    url_for_parsing = normalized_url
    if not parsed.scheme:
        url_for_parsing = f"https://{normalized_url.lstrip('/')}"
        parsed = urlparse(url_for_parsing)
    scheme = (parsed.scheme or "").lower()
    allow_http = bool(include_http_fallback_for_https) or scheme != "https"
    host = parsed.hostname or parsed.netloc
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    suffix = f"{path}{query}{fragment}"
    host_lower = host.lower()
    candidates: list[str] = [normalized_url]
    if host:
        candidates.append(f"https://{host}{suffix}")
        if allow_http:
            candidates.append(f"http://{host}{suffix}")
    if host_lower.startswith("www."):
        base_host = host[4:]
        candidates.append(f"https://{base_host}{suffix}")
        if allow_http:
            candidates.append(f"http://{base_host}{suffix}")
    else:
        labels = [label for label in host_lower.split(".") if label]
        has_country_tld = bool(labels) and len(labels[-1]) == 2
        common_sld = {"ac", "co", "com", "edu", "gov", "net", "org"}
        allow_www = len(labels) == 2 or (
            len(labels) == 3 and has_country_tld and labels[-2] in common_sld
        )
        if allow_www:
            candidates.append(f"https://www.{host}{suffix}")
            if allow_http:
                candidates.append(f"http://www.{host}{suffix}")
    seen: set[str] = set()
    variants: list[str] = []
    for candidate in candidates:
        normalized = candidate.lower()
        if normalized not in seen and candidate:
            seen.add(normalized)
            variants.append(candidate)
    return variants


async def validate_fetch_url(
    runtime_flags: RuntimeFlagsViewProtocol,
    dns_timeout_sec: float,
    url: str,
    *,
    source: str,
    block_private_networks: bool = True,
) -> tuple[str, str | None]:
    normalized = normalize_http_url(url)
    if is_offline_mode_enabled(runtime_flags):
        pinned_ip = await validate_local_only_url(
            runtime_flags,
            normalized,
            source=source,
        )
        return (normalized, pinned_ip)
    pinned_ip = await enforce_url_network_policy(
        normalized,
        block_private_networks=block_private_networks,
        dns_timeout_sec=dns_timeout_sec,
        source=source,
    )
    return (normalized, pinned_ip)
