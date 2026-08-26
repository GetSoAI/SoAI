"""SoAI - OpenAI storage owner resolution helpers [backend/features/api/routes/openai/storage_owner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.users.user_id import coerce_optional_user_id
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.openai.anonymous_owner_key import resolve_anonymous_owner_key
from features.api.runtime.openai_request_state import (
    resolve_openai_api_key_context_optional,
)

__all__ = (
    "resolve_file_storage_owner",
    "resolve_request_context_user_id",
    "resolve_responses_storage_owner",
)


def resolve_request_context_user_id(request: Request) -> int | None:
    try:
        context = request.state.context
    except AttributeError:
        context = None
    return coerce_optional_user_id(context)


def _resolve_storage_owner(
    request: Request,
    *,
    user_id: int | None,
) -> tuple[str | None, int | None]:
    normalized_user_id = user_id if user_id is not None and user_id > 0 else None
    api_key_context = resolve_openai_api_key_context_optional(request)
    if api_key_context is not None:
        api_key_id = api_key_context.key_id
    elif normalized_user_id is not None:
        api_key_id = None
    else:
        api_key_id = resolve_anonymous_owner_key(request)
    return (coerce_optional_trimmed_str(api_key_id), normalized_user_id)


def resolve_file_storage_owner(request: Request) -> tuple[str | None, int | None]:
    return _resolve_storage_owner(
        request,
        user_id=resolve_request_context_user_id(request),
    )


def resolve_responses_storage_owner(request: Request) -> tuple[str | None, int | None]:
    return _resolve_storage_owner(
        request,
        user_id=resolve_request_context_user_id(request),
    )
