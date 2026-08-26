"""SoAI - OpenAI anonymous owner key resolution helpers [backend/features/api/routes/openai/anonymous_owner_key.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.openai.anonymous_owner_tokens import (
    generate_anonymous_owner_token,
    normalize_anonymous_owner_token,
)

__all__ = ("resolve_anonymous_owner_key",)

_ANON_TOKEN_HEADER = "x-soai-anon-token"
_ANON_TOKEN_COOKIE = "soai-anon-token"


def _resolve_anonymous_owner_token_from_request(request: Request) -> str | None:
    header_value = request.headers.get(_ANON_TOKEN_HEADER)
    token = normalize_anonymous_owner_token(header_value)
    if token is not None:
        return token
    cookie_value = request.cookies.get(_ANON_TOKEN_COOKIE)
    return normalize_anonymous_owner_token(cookie_value)


def _resolve_issued_anonymous_owner_token(request: Request) -> str | None:
    try:
        token_value = request.state.issued_anonymous_owner_token
    except AttributeError:
        return None
    return normalize_anonymous_owner_token(token_value)


def _issue_anonymous_owner_token(request: Request) -> str:
    issued = generate_anonymous_owner_token()
    request.state.issued_anonymous_owner_token = issued
    return issued


def resolve_anonymous_owner_key(request: Request) -> str:
    token = _resolve_anonymous_owner_token_from_request(request)
    if token is None:
        token = _resolve_issued_anonymous_owner_token(request)
    if token is None:
        token = _issue_anonymous_owner_token(request)
    return f"__anon__:{token}"
