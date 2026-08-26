"""SoAI - Request context helpers for cancellation propagation [backend/core/concurrency/context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.protocols import CancellationContextProtocol
from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_ids import normalize_cancellation_id

__all__ = (
    "create_system_cancellation_id",
    "get_context_cancellation_id",
    "require_context_cancellation_id",
)


def get_context_cancellation_id(context: CancellationContextProtocol | None) -> str | None:
    if context is None:
        return None
    try:
        cancellation_id = context.cancellation_id
    except AttributeError:
        return None
    if cancellation_id is None:
        return None
    normalized = normalize_cancellation_id(cancellation_id)
    return normalized


def require_context_cancellation_id(context: CancellationContextProtocol | None) -> str:
    cancellation_id = get_context_cancellation_id(context)
    if not cancellation_id:
        raise ValidationError(
            "Request context is missing a valid cancellation_id for cancellation.",
        )
    return cancellation_id


def create_system_cancellation_id(label: str) -> str:
    normalized = str(label or "").strip().lower().replace(" ", "_") or "system"
    return create_system_id(subsystem="concurrency", owner=normalized, include_random_suffix=True)
