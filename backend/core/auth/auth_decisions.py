"""SoAI - WebUI authentication decision types [backend/core/auth/auth_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from fastapi import Response, status
from fastapi.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.errors.public_projection import build_error_payload
from core.state.access import AccessAction
from core.system_api.anthropic_error_types import resolve_anthropic_error_type
from core.system_api.request_paths import (
    is_anthropic_api_request_path,
    is_openai_api_request_path,
)
from core.timing.durations import ms_to_seconds_ceil
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AuthenticationDecision",
    "resolve_action_set",
    "resolve_openai_api_key_action_set",
)

_CACHE_CONTROL_HEADER = "Cache-Control"
_NO_STORE_CACHE_CONTROL = "no-store"


def _build_access_action_lookup() -> MappingProxyType[str, AccessAction]:
    builder: dict[str, AccessAction] = {}
    for action in AccessAction:
        builder[action.value] = action
        builder[action.value.upper()] = action
        builder[action.value.lower()] = action
        builder[action.name] = action
        builder[action.name.upper()] = action
        builder[action.name.lower()] = action
    return MappingProxyType(builder)


@dataclass(frozen=True, slots=True)
class AuthenticationDecision:
    continue_request: bool
    auth_method: str
    user: JSONDict | None = None
    token_payload: JSONDict | None = None
    status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    granted_actions: frozenset[AccessAction] | None = None
    failure_category: str | None = None
    rate_limit_reset: int | None = None
    headers: dict[str, str] | None = None
    trace_id: str | None = None

    def _resolve_headers(self) -> dict[str, str] | None:
        headers = dict(self.headers or {})
        if all(header_name.lower() != "cache-control" for header_name in headers):
            headers[_CACHE_CONTROL_HEADER] = _NO_STORE_CACHE_CONTROL
        if self.rate_limit_reset:
            retry_after_ms = max(self.rate_limit_reset - epoch_ms(), 0)
            retry_after_seconds = ms_to_seconds_ceil(retry_after_ms)
            if "Retry-After" not in headers:
                headers["Retry-After"] = str(retry_after_seconds)
        return headers

    def _to_openai_error_response(self) -> Response:
        status_code = int(self.status_code or status.HTTP_401_UNAUTHORIZED)
        message = str(self.error_message or "Authentication required.")
        error_type = str(self.error_type or "authentication_error")
        payload = {
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": None,
            },
        }
        return JSONResponse(
            status_code=status_code,
            content=payload,
            headers=self._resolve_headers(),
        )

    def _to_anthropic_error_response(self) -> Response:
        status_code = int(self.status_code or status.HTTP_401_UNAUTHORIZED)
        return JSONResponse(
            status_code=status_code,
            content={
                "type": "error",
                "error": {
                    "type": resolve_anthropic_error_type(
                        status_code=status_code,
                        upstream_error_type=self.error_type,
                    ),
                    "message": str(self.error_message or "Authentication required."),
                },
            },
            headers=self._resolve_headers(),
        )

    def to_response_for_path(self, path: str) -> Response | None:
        if self.continue_request:
            return None
        normalized = str(path or "")
        if is_anthropic_api_request_path(normalized):
            return self._to_anthropic_error_response()
        if is_openai_api_request_path(normalized):
            return self._to_openai_error_response()
        return self.to_response()

    def to_response(self) -> Response | None:
        if self.continue_request:
            return None
        status_code = self.status_code or status.HTTP_401_UNAUTHORIZED
        payload = build_error_payload(
            self.error_message or "Authentication required.",
            code=self.error_type or "authentication_error",
            trace_id=self.trace_id,
        )
        if self.failure_category:
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                error_payload["category"] = self.failure_category
        return JSONResponse(
            status_code=status_code,
            content=payload,
            headers=self._resolve_headers(),
        )


def resolve_action_set(
    scopes: Collection[str],
) -> frozenset[AccessAction]:
    strict = isinstance(scopes, tuple)
    lookup = _build_access_action_lookup()
    resolved: set[AccessAction] = set()
    unknown: list[str] = []
    for scope in scopes or ():
        text = str(scope or "").strip()
        if not text:
            continue
        action = lookup.get(text)
        if action is None:
            action = lookup.get(text.upper()) or lookup.get(text.lower())
        if action is None:
            if strict:
                unknown.append(text)
            continue
        resolved.add(action)
    if strict:
        if unknown:
            raise ValidationError(f"Unknown access scope(s): {', '.join(unknown)}")
        if not resolved:
            raise ValidationError("No valid access scopes supplied.")
        return frozenset(resolved)
    if not resolved:
        return frozenset({AccessAction.OPENAI_API})
    return frozenset(resolved)


def resolve_openai_api_key_action_set(
    scopes: Iterable[str] | None,
) -> frozenset[AccessAction]:
    if scopes is None:
        return frozenset({AccessAction.OPENAI_API})
    values = tuple(scopes)
    if not values:
        return frozenset({AccessAction.OPENAI_API})
    resolved = resolve_action_set(values)
    invalid_actions = resolved.difference({AccessAction.OPENAI_API})
    if invalid_actions:
        invalid_text = ", ".join(sorted(action.value for action in invalid_actions))
        raise ValidationError(
            f"OpenAI API keys only support the OPENAI_API scope. Unsupported scope(s): {invalid_text}",
        )
    return resolved
