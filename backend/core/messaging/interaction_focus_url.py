"""SoAI - Authenticated Chat interaction focus URL [backend/core/messaging/interaction_focus_url.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import quote, urlencode

from core.network.urls import normalize_base_url
from core.oauth.management_urls import require_https_url

__all__ = ("build_messaging_interaction_focus_url",)


def build_messaging_interaction_focus_url(
    *,
    public_origin: str,
    conv_id: str,
    focus_nonce: str,
) -> str:
    normalized_origin = normalize_base_url(public_origin)
    require_https_url(normalized_origin, "SERVER.PUBLIC_ORIGIN")
    query = urlencode({"interaction_focus": focus_nonce})
    return f"{normalized_origin}/chat/conversation/{quote(conv_id, safe='')}?{query}"
