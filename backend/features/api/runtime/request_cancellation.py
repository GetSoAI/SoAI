"""SoAI - API request cancellation identifier resolution [backend/features/api/runtime/request_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.soai_identifiers import create_system_id
from core.tasks.cancellation_ids import normalize_cancellation_id

if TYPE_CHECKING:
    from core.runtime.protocols import ConnectionProtocol

__all__ = ("resolve_request_cancellation_id_or_create",)


def resolve_request_cancellation_id_or_create(
    request: ConnectionProtocol,
    *,
    subsystem: str,
    trace_id: str | None,
    owner: str,
) -> str:
    try:
        context = request.state.context
    except AttributeError:
        context = None
    if context is None:
        cancellation_id_value = None
        trace_id_value = None
    else:
        try:
            cancellation_id_value = context.cancellation_id
        except AttributeError:
            cancellation_id_value = None
        try:
            trace_id_value = context.trace_id
        except AttributeError:
            trace_id_value = None
    cancellation_id = normalize_cancellation_id(cancellation_id_value)
    if cancellation_id:
        return cancellation_id
    resolved_trace_id = str(trace_id or trace_id_value or "").strip()
    resolved_owner = str(resolved_trace_id or owner).strip()
    if not resolved_owner:
        resolved_owner = owner
    return create_system_id(
        subsystem=subsystem,
        owner=resolved_owner,
        include_random_suffix=True,
    )
