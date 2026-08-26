"""SoAI - WebUI cookie operations [backend/core/auth/cookies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.auth.csrf_tokens import SOAI_CSRF_HEADER_NAME, create_csrf_token
from core.auth.jwt_claims import (
    JWT_ALGORITHM,
    AccessTokenRecord,
    create_access_token_record,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.runtime.proxy_headers import normalize_scheme_value
from core.timing.epoch import epoch_ms
from core.timing.formatting import timestamp_ms_to_utc_datetime

if TYPE_CHECKING:
    from fastapi import Response

__all__ = (
    "create_auth_token_record",
    "determine_secure_cookie",
    "resolve_webui_cookie_names",
    "set_auth_cookie_record",
    "set_csrf_cookie",
    "WebuiCookieNames",
)


@dataclass(frozen=True, slots=True)
class WebuiCookieNames:
    auth: str
    csrf: str


def resolve_webui_cookie_names(request_scheme: str | None) -> WebuiCookieNames:
    scheme = normalize_scheme_value(request_scheme)
    if scheme == "http":
        return WebuiCookieNames(auth="soai-http-token", csrf="soai-http-csrf")
    if scheme == "https":
        return WebuiCookieNames(auth="__Host-soai-token", csrf="__Host-soai-csrf")
    raise StateError("WebUI cookie transport scheme is unavailable.")


def determine_secure_cookie(config: ConfigProtocol, *, request_scheme: str | None = None) -> bool:
    cookie_override = config.get_bool("SERVER.WEBUI.COOKIE_SECURE")
    if cookie_override:
        return True
    scheme = (request_scheme or "").strip().lower()
    if request_scheme is not None:
        if scheme == "https":
            return True
        if scheme == "http":
            return False
    if config.get_bool("SERVER.HTTP.SSL.TLS_ENABLED"):
        return True
    return bool(
        config.get_str("SERVER.HTTP.SSL.CERT_FILE") and config.get_str("SERVER.HTTP.SSL.KEY_FILE"),
    )


def create_auth_token_record(
    config: ConfigProtocol,
    user_id: int,
    username: str,
    *,
    password_revision: int,
    secret_key: str,
    algorithm: str = JWT_ALGORITHM,
) -> AccessTokenRecord:
    expire_mins = config.get_int("SERVER.WEBUI.ACCESS_TOKEN_EXPIRE_MINUTES")
    return create_access_token_record(
        secret_key,
        data={"uid": user_id, "sub": username, "pwd_rev": password_revision},
        expires_delta_minutes=expire_mins,
        algorithm=algorithm,
    )


def _remaining_cookie_seconds(expires_at_ms: int) -> int:
    remaining_ms = max(0, expires_at_ms - epoch_ms())
    return (remaining_ms + 999) // 1000


def set_auth_cookie_record(
    response: Response,
    config: ConfigProtocol,
    token_record: AccessTokenRecord,
    *,
    cookie_names: WebuiCookieNames,
    secret_key: str,
    secure_cookie: bool | None = None,
    csrf_token: str | None = None,
) -> None:
    secure_cookie_flag = (
        determine_secure_cookie(config, request_scheme=None)
        if secure_cookie is None
        else bool(secure_cookie)
    )
    response.set_cookie(
        key=cookie_names.auth,
        value=token_record.token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie_flag,
        path="/",
        max_age=_remaining_cookie_seconds(token_record.expires_at_ms),
        expires=timestamp_ms_to_utc_datetime(token_record.expires_at_ms),
    )
    set_csrf_cookie(
        response,
        config,
        cookie_names=cookie_names,
        secret_key=secret_key,
        secure_cookie=secure_cookie_flag,
        token=csrf_token,
        expires_at_ms=token_record.expires_at_ms,
    )


def set_csrf_cookie(
    response: Response,
    config: ConfigProtocol,
    *,
    cookie_names: WebuiCookieNames,
    secret_key: str,
    secure_cookie: bool | None = None,
    token: str | None = None,
    expires_at_ms: int | None = None,
) -> str:
    expire_mins = config.get_int("SERVER.WEBUI.ACCESS_TOKEN_EXPIRE_MINUTES")
    resolved_token = create_csrf_token(secret_key) if token is None else token
    secure_cookie_flag = (
        determine_secure_cookie(config, request_scheme=None)
        if secure_cookie is None
        else bool(secure_cookie)
    )
    response.set_cookie(
        key=cookie_names.csrf,
        value=resolved_token,
        httponly=False,
        samesite="lax",
        secure=secure_cookie_flag,
        path="/",
        max_age=(
            expire_mins * 60 if expires_at_ms is None else _remaining_cookie_seconds(expires_at_ms)
        ),
        expires=(None if expires_at_ms is None else timestamp_ms_to_utc_datetime(expires_at_ms)),
    )
    response.headers[SOAI_CSRF_HEADER_NAME] = resolved_token
    return resolved_token
