"""SoAI - Messaging public callback URL contracts [backend/core/messaging/callback_urls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from core.errors.exceptions import ValidationError
from core.messaging.account_validation import require_messaging_account_id
from core.network.urls import normalize_base_url
from core.oauth.management_urls import require_https_url
from core.system_api.route_paths import SOAI_MESSAGING_PREFIX

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform

__all__ = ("build_messaging_callback_url", "fingerprint_messaging_callback_url")


def build_messaging_callback_url(
    *,
    public_origin: str,
    platform: MessagingPlatform,
    account_id: str,
) -> str:
    normalized_origin = normalize_base_url(public_origin)
    require_https_url(normalized_origin, "SERVER.PUBLIC_ORIGIN")
    if platform not in ("telegram", "whatsapp"):
        raise ValidationError("Discord does not use a public callback URL.")
    query = urlencode({"account_id": require_messaging_account_id(account_id)})
    return f"{normalized_origin}{SOAI_MESSAGING_PREFIX}/{platform}/webhook?{query}"


def fingerprint_messaging_callback_url(url: str) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise ValidationError("Messaging callback URL is required.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
