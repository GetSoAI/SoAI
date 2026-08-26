"""SoAI - API runtime restart checks [backend/features/api/runtime/restart.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.logging.trace import get_logger
from core.system_api.request_paths import get_scope_path
from features.api.runtime.context import require_request_context, resolve_api_context

__all__ = (
    "check_restart_status",
    "check_restart_status_allow_backend",
)

LOGGER_NAME = "SoAI.features.api.restart"


async def check_restart_status(request: Request) -> None:
    api_context = resolve_api_context(request)
    if not api_context.dependencies.restart_pending.is_set():
        return
    request.state.restart_required = True


async def check_restart_status_allow_backend(request: Request) -> None:
    api_context = resolve_api_context(request)
    if not api_context.dependencies.restart_pending.is_set():
        return
    request.state.restart_required = True
    trace_id = "no-trace"
    request_context = require_request_context(request)
    trace_id_value = request_context.trace_id
    if isinstance(trace_id_value, str) and trace_id_value:
        trace_id = trace_id_value
    get_logger(LOGGER_NAME).debug(
        "[%s] Allowing API access to %s %s while restart_pending is set (explicit allow).",
        trace_id,
        request.method,
        get_scope_path(request.scope),
    )
