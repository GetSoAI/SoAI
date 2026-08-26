"""SoAI - API security secure transport enforcement [backend/features/api/middleware/security/secure_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import State

from core.errors.exceptions import StateError
from core.logging.trace import get_context_trace_id
from core.runtime.proxy_headers import resolve_request_scheme
from core.runtime.request_context import RequestContext
from core.runtime.state_access import read_request_state_value, read_state_flag
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)

__all__ = ("enforce_secure_transport",)


def enforce_secure_transport(request: Request) -> JSONResponse | None:
    state = request.app.state
    secure_transport_required = False
    if isinstance(state, State):
        secure_transport_required = read_state_flag(state, "secure_transport_required")
    if not secure_transport_required:
        return None
    try:
        scheme = resolve_request_scheme(request)
    except StateError:
        scheme = "http"
    if scheme == "https":
        return None
    context = read_request_state_value(request, "context", RequestContext)
    trace_id = get_context_trace_id(context)
    return build_boundary_error_json_response_for_request(
        request,
        status_code=status.HTTP_403_FORBIDDEN,
        message="Secure transport is required for this request.",
        soai_code="insecure_transport",
        openai_code="insecure_transport",
        trace_id=trace_id,
    )
