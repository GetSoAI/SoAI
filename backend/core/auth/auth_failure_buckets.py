"""SoAI - Auth failure bucket helpers [backend/core/auth/auth_failure_buckets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "build_auth_failure_buckets",
    "build_webui_login_failure_buckets",
    "WEBUI_LOGIN_IP_NAME_PREFIX",
    "WEBUI_LOGIN_USER_PREFIX",
)

WEBUI_LOGIN_IP_NAME_PREFIX = "webui_login:"
WEBUI_LOGIN_USER_PREFIX = "webui_login_user:"


def _normalize_login_identifier(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    if not normalized:
        return "unknown"
    return normalized[:128]


def build_auth_failure_buckets(
    *,
    ip_bucket_prefix: str,
    token_bucket_prefix: str,
    client_ip: str,
    provided_token: str | None,
    token_fingerprint: str | None = None,
) -> tuple[str, ...]:
    ip_prefix = str(ip_bucket_prefix or "").strip()
    token_prefix = str(token_bucket_prefix or "").strip()
    if not ip_prefix or not token_prefix:
        raise ValidationError("Auth bucket prefixes must be provided.")
    client_identifier = str(client_ip or "").strip() or "unknown"
    buckets: list[str] = [f"{ip_prefix}:{client_identifier}"]
    token_value = (provided_token or "").strip()
    if not token_value:
        buckets.append(f"{token_prefix}:{client_identifier}:missing")
        return tuple(buckets)
    fingerprint = (token_fingerprint or "").strip()
    if not fingerprint:
        raise ValidationError("Token fingerprint must be provided for token auth buckets.")
    buckets.append(f"{token_prefix}:{client_identifier}:{fingerprint[:12]}")
    return tuple(buckets)


def build_webui_login_failure_buckets(client_ip: str, username: str | None) -> tuple[str, ...]:
    client_identifier = str(client_ip or "").strip() or "unknown"
    normalized_username = _normalize_login_identifier(username)
    ip_bucket = f"webui_login_ip:{client_identifier}"
    if normalized_username == "unknown":
        return (ip_bucket,)
    return (
        ip_bucket,
        f"{WEBUI_LOGIN_IP_NAME_PREFIX}{client_identifier}:{normalized_username}",
        f"{WEBUI_LOGIN_USER_PREFIX}{normalized_username}",
    )
