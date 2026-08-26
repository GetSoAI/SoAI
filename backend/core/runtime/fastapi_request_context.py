"""SoAI - FastAPI request context setup shared across the backend [backend/core/runtime/fastapi_request_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from core.runtime.protocols import RequestProtocol
from core.runtime.proxy_headers import extract_real_client_ip
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_request_id

__all__ = (
    "initialize_request_state_fields",
    "setup_request_context",
)


def initialize_request_state_fields(request: RequestProtocol) -> None:
    request.state.client_host = None
    request.state.auth_method = "none"
    request.state.user = None
    request.state.token_payload = None
    request.state.granted_actions = None
    request.state.auth_failure_category = None
    request.state.access_state = None
    request.state.openai_api_key_id = None
    request.state.openai_api_key_quota_reservation = None
    request.state.rate_limit_breach = None
    request.state.restart_required = False
    request.state.api_context = None
    request.state.openai_stored_chat_completion_request_json = None


def setup_request_context(request: RequestProtocol, prefix: str) -> float:
    trace_id = create_request_id(prefix=prefix)
    client_ip = extract_real_client_ip(request)
    request.state.context = RequestContext(
        trace_id=trace_id,
        client_ip=client_ip,
        task_id=trace_id,
        cancellation_id=trace_id,
    )
    initialize_request_state_fields(request)
    return time.monotonic()
