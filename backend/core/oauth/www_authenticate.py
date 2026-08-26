"""SoAI - WWW-Authenticate Bearer challenge parsing [backend/core/oauth/www_authenticate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.oauth.types import OAuthChallenge

__all__ = ("parse_www_authenticate_bearer_challenge",)


def parse_www_authenticate_bearer_challenge(header_value: str | None) -> OAuthChallenge | None:
    if not header_value or not isinstance(header_value, str):
        return None
    bearer_pos = _find_bearer_scheme(header_value)
    if bearer_pos is None:
        return None
    params_raw = header_value[bearer_pos:]
    params = _parse_auth_params(params_raw)
    if not params:
        return OAuthChallenge(None, None, None, None)
    return OAuthChallenge(
        resource_metadata=_coerce_str(params.get("resource_metadata")),
        scope=_coerce_str(params.get("scope")),
        error=_coerce_str(params.get("error")),
        error_description=_coerce_str(params.get("error_description")),
    )


def _find_bearer_scheme(value: str) -> int | None:
    lowered = value.lower()
    idx = lowered.find("bearer")
    if idx < 0:
        return None
    end = idx + len("bearer")
    if idx > 0 and lowered[idx - 1].isalnum():
        return None
    if end < len(lowered) and lowered[end].isalnum():
        return None
    return end


def _parse_auth_params(value: str) -> dict[str, str]:
    raw = value.strip()
    if raw.startswith(","):
        raw = raw[1:].lstrip()
    if raw.startswith(" "):
        raw = raw.lstrip()
    parts = _split_commas(raw)
    result: dict[str, str] = {}
    for part in parts:
        key, sep, rest = part.partition("=")
        if not sep:
            continue
        key_name = key.strip().lower()
        raw_value = rest.strip()
        if not key_name:
            continue
        result[key_name] = _unquote(raw_value)
    return result


def _split_commas(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    escape = False
    for ch in value:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\" and in_quotes:
            current.append(ch)
            escape = True
            continue
        if ch == '"':
            current.append(ch)
            in_quotes = not in_quotes
            continue
        if ch == "," and not in_quotes:
            candidate = "".join(current).strip()
            if candidate:
                parts.append(candidate)
            current = []
            continue
        current.append(ch)
    trailing = "".join(current).strip()
    if trailing:
        parts.append(trailing)
    return parts


def _unquote(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        inner = stripped[1:-1]
        inner = inner.replace('\\"', '"')
        inner = inner.replace("\\\\", "\\")
        return inner
    return stripped


def _coerce_str(value: str | None) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
