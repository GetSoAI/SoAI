"""SoAI - OpenAI API key quota enforcement middleware for /v1/* [backend/features/api/middleware/openai_api_key_quotas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.system_api.request_paths import (
    get_scope_path,
    is_anthropic_api_request_path,
    is_public_inference_api_request_path,
)
from core.timing.epoch import epoch_ms
from features.api.openai.api_key_quota_http_responses import (
    build_insufficient_quota_response,
)
from features.api.routes.anthropic.error_responses import project_error_response
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.context import resolve_api_context
from features.api.runtime.openai_request_state import (
    resolve_openai_api_key_context_optional,
)
from features.api.runtime.quota_reservation_decisions import (
    parse_quota_reservation_decision,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.types.json import JSONDict

__all__ = ("OpenAIAPIKeyQuotaMiddleware",)

LOGGER_NAME = "SoAI.features.api.openai_api_key_quotas"
OPERATION = "api_middleware.openai_api_key_quotas.finalize"


def _resolve_request_quota_actual_units(request: Request) -> int:
    try:
        rate_limit_breach = request.state.rate_limit_breach
    except AttributeError:
        rate_limit_breach = None
    return 0 if rate_limit_breach is not None else 1


class OpenAIAPIKeyQuotaMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def _finalize_request_quota_noncritical(
        self,
        *,
        database_api_keys: DatabaseAPIKeysProtocol,
        key_id: str,
        reservation: JSONDict,
        path: str,
        actual_units: int,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await uncancel_then_cleanup(
                database_api_keys.finalize_quota_reservation(
                    key_id,
                    reservation,
                    actual_units=int(actual_units),
                    now_ts=epoch_ms(),
                ),
            )
        except asyncio.CancelledError as cancelled_error:
            coerced = coerce_to_soai_error(
                cancelled_error,
                operation="api_middleware.openai_api_key_quotas.finalize",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Request quota finalization interrupted by task cancellation (non-critical).",
                operation=OPERATION,
                details={"key_id": key_id, "path": path},
                level="warning",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="api_middleware.openai_api_key_quotas.finalize",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Request quota finalization failed (non-critical).",
                operation=OPERATION,
                details={"key_id": key_id, "path": path},
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="api_middleware.openai_api_key_quotas.finalize",
            )
            log_exception(
                logger,
                coerced,
                message="Failed to finalize request quota reservation (unexpected, non-critical).",
                operation=OPERATION,
                details={"key_id": key_id, "path": path},
                level="error",
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        path = get_scope_path(request.scope)
        if not is_public_inference_api_request_path(path):
            await self.app(scope, receive, send)
            return
        context = resolve_openai_api_key_context_optional(request)
        if context is None:
            await self.app(scope, receive, send)
            return
        key_id = context.key_id
        now_ts = epoch_ms()
        trace_id = context.trace_id
        api_context = resolve_api_context(request)
        database_api_keys = api_context.dependencies.webui_manager.database_api_keys
        client_ip = resolve_client_host(request, default="")
        reservation_result = await database_api_keys.reserve_quota_units_for_mode(
            key_id,
            "requests",
            1,
            now_ts,
            client_ip=client_ip,
        )
        decision = parse_quota_reservation_decision(reservation_result, now_ts_ms=now_ts)
        if not decision.allowed:
            response: Response = build_insufficient_quota_response(
                trace_id=trace_id,
                window=decision.window,
                retry_at_ms=int(decision.retry_at_ms),
                now_ts_ms=int(now_ts),
                status=decision.status,
            )
            if is_anthropic_api_request_path(path):
                response = project_error_response(response)
            await response(scope, receive, send)
            return
        reservation = decision.reservation
        if reservation is None:
            await self.app(scope, receive, send)
            return
        finalized = False
        finalize_lock = asyncio.Lock()

        async def finalize_once() -> None:
            nonlocal finalized
            async with finalize_lock:
                if finalized:
                    return
                try:
                    await uncancel_then_cleanup(
                        self._finalize_request_quota_noncritical(
                            database_api_keys=database_api_keys,
                            key_id=key_id,
                            reservation=reservation,
                            path=path,
                            actual_units=_resolve_request_quota_actual_units(request),
                        ),
                    )
                finally:
                    finalized = True

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                await finalize_once()
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            await finalize_once()
