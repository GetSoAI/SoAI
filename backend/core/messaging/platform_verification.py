"""SoAI - Messaging platform webhook verification helpers [backend/core/messaging/platform_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac

__all__ = (
    "parse_whatsapp_verification_challenge",
    "verify_shared_secret",
    "verify_telegram_secret",
    "verify_whatsapp_signature",
)


def verify_shared_secret(expected_secret: str | None, provided_secret: str | None) -> bool:
    expected = str(expected_secret or "").strip()
    if not expected:
        return False
    if provided_secret is None:
        return False
    provided = provided_secret.strip()
    if not provided:
        return False
    return hmac.compare_digest(expected, provided)


def verify_telegram_secret(expected_secret: str | None, provided_secret: str | None) -> bool:
    return verify_shared_secret(expected_secret, provided_secret)


def verify_whatsapp_signature(
    *,
    app_secret: str | None,
    signature_header: str | None,
    raw_body: bytes,
) -> bool:
    normalized_secret = str(app_secret or "").strip()
    if not normalized_secret:
        return False
    if signature_header is None:
        return False
    normalized_header = signature_header.strip()
    if not normalized_header.startswith("sha256="):
        return False
    digest = hmac.new(
        normalized_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(normalized_header.removeprefix("sha256="), digest)


def parse_whatsapp_verification_challenge(
    *,
    verify_token: str | None,
    mode: str | None,
    token: str | None,
    challenge: str | None,
) -> str | None:
    normalized_verify_token = str(verify_token or "").strip()
    if not normalized_verify_token:
        return None
    if mode != "subscribe":
        return None
    if token is None or challenge is None:
        return None
    if not hmac.compare_digest(normalized_verify_token, token.strip()):
        return None
    return challenge
