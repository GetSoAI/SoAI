"""SoAI - Browser URL wait pattern normalization [backend/mcp/tools/browser/url_wait_patterns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from ipaddress import ip_address
from re import Pattern
from urllib.parse import urlsplit

__all__ = (
    "build_url_prefix_wait_pattern",
    "build_url_wait_pattern",
)


def build_url_wait_pattern(pattern: str) -> Pattern[str]:
    normalized = str(pattern or "").strip()
    optional_www_pattern = _build_optional_www_wait_pattern(normalized)
    if optional_www_pattern is not None:
        return optional_www_pattern
    return re.compile(f"^{_glob_to_regex(normalized)}$")


def _build_optional_www_wait_pattern(pattern: str) -> Pattern[str] | None:
    parsed = urlsplit(pattern)
    netloc = parsed.netloc
    if not parsed.scheme or not netloc:
        return None
    if "*" in netloc or "?" in netloc or "@" in netloc or netloc.startswith("["):
        return None
    host = netloc.split(":", 1)[0]
    suffix = netloc[len(host) :]
    if not host or host.startswith("www.") or "." not in host or _is_ip_address(host):
        return None
    path_and_after = pattern[len(f"{parsed.scheme}://{netloc}") :]
    regex = (
        f"^{re.escape(parsed.scheme)}://"
        f"(?:www\\.)?{re.escape(host)}{re.escape(suffix)}"
        f"{_glob_to_regex(path_and_after)}$"
    )
    return re.compile(regex)


def _is_ip_address(host: str) -> bool:
    try:
        ip_address(host)
    except ValueError:
        return False
    return True


def _glob_to_regex(pattern: str) -> str:
    regex_parts: list[str] = []
    previous_was_star = False
    for character in pattern:
        if character == "*":
            if not previous_was_star:
                regex_parts.append(".*")
            previous_was_star = True
        elif character == "?":
            regex_parts.append(".")
            previous_was_star = False
        else:
            regex_parts.append(re.escape(character))
            previous_was_star = False
    return "".join(regex_parts)


def build_url_prefix_wait_pattern(prefix: str) -> Pattern[str]:
    normalized = str(prefix or "").strip()
    return re.compile(f"^{re.escape(normalized)}.*$")
