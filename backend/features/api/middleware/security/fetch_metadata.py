"""SoAI - Fetch Metadata request hardening helpers [backend/features/api/middleware/security/fetch_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from features.api.middleware.security.csrf import is_unsafe_browser_method

__all__ = ("should_block_cross_site_cookie_request",)


def should_block_cross_site_cookie_request(request: Request, auth_method: str | None) -> bool:
    if auth_method not in {"jwt_cookie", "jwt_cookie_rotation_recovery"}:
        return False
    if not is_unsafe_browser_method(request.method):
        return False
    fetch_site = request.headers.get("sec-fetch-site")
    if not isinstance(fetch_site, str):
        return False
    return fetch_site.strip().casefold() == "cross-site"
