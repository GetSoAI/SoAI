"""SoAI - Request trace ID extraction [backend/core/runtime/request_trace_id.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.protocols import ConnectionProtocol
from core.runtime.request_context import RequestContext
from core.runtime.state_access import read_state_value

__all__ = ("get_request_trace_id",)


def get_request_trace_id(request: ConnectionProtocol) -> str | None:
    context = read_state_value(request.state, "context", RequestContext)
    if context is None:
        return None
    trace_id_value = context.trace_id
    normalized = trace_id_value.strip()
    return normalized or None
