"""SoAI - Ownership/cancellation resolution for request-scoped operations [backend/core/runtime/ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.context import (
    create_system_cancellation_id,
    require_context_cancellation_id,
)
from core.errors.exceptions import ValidationError
from core.runtime.protocols import RequestOwnershipContextProtocol

__all__ = (
    "resolve_context_ownership",
    "resolve_http_owner_id",
)


def resolve_http_owner_id(context: RequestOwnershipContextProtocol) -> str:
    try:
        user_id = context.user_id
    except AttributeError:
        user_id = 0
    if isinstance(user_id, bool):
        resolved_user_id = 0
    else:
        try:
            resolved_user_id = int(user_id or 0)
        except (TypeError, ValueError) as exception:
            raise ValidationError("Request context user_id must be an integer.") from exception
    if resolved_user_id < 0:
        raise ValidationError("Request context user_id must be >= 0.")
    return f"http_user:{resolved_user_id}"


def resolve_context_ownership(
    context: RequestOwnershipContextProtocol | None,
) -> tuple[int, str, str, str]:
    if context is None:
        return (0, "system", "system", create_system_cancellation_id("system_task"))
    try:
        user_id_raw = context.user_id
    except AttributeError:
        user_id_raw = 0
    user_id = 0 if isinstance(user_id_raw, bool) else int(user_id_raw or 0)
    if user_id:
        cancellation_id = require_context_cancellation_id(context)
        return (user_id, resolve_http_owner_id(context), "http_request", cancellation_id)
    return (0, "system", "system", create_system_cancellation_id("system_task"))
