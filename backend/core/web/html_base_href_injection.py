"""SoAI - HTML base href injection helper [backend/core/web/html_base_href_injection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import urlparse

__all__ = ("inject_base_href",)


def inject_base_href(html: str, *, base_href: str) -> str:
    normalized = html or ""
    if "<base" in normalized.lower():
        return normalized
    parsed = urlparse(base_href)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return normalized
    base_tag = f'<base href="{base_href}">'
    lower = normalized.lower()
    head_index = lower.find("<head")
    if head_index >= 0:
        head_close = lower.find(">", head_index)
        if head_close >= 0:
            return normalized[: head_close + 1] + base_tag + normalized[head_close + 1 :]
    html_index = lower.find("<html")
    if html_index >= 0:
        html_close = lower.find(">", html_index)
        if html_close >= 0:
            insertion = f"<head>{base_tag}</head>"
            return normalized[: html_close + 1] + insertion + normalized[html_close + 1 :]
    return base_tag + normalized
