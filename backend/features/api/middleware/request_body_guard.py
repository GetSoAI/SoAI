"""SoAI - Request body ownership and size middleware [backend/features/api/middleware/request_body_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.system_api.request_paths import (
    get_scope_path,
    is_public_inference_api_request_path,
)
from features.api.request_body_policy import RequestBodyPolicy
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)
from features.api.runtime.request_media_types import is_multipart_media_type

__all__ = ("RequestBodyGuardMiddleware", "claim_streaming_multipart_body")

LOGGER_NAME = "SoAI.features.api.request_body_guard"
OPERATION = "api.request_body_guard.response_started"
_STREAMING_MULTIPART_OWNER_SCOPE_KEY = "soai.streaming_multipart_body_owner"


@dataclass(frozen=True, slots=True)
class _BodyViolation:
    status_code: int
    code: str
    message: str


class _BodyViolationSignal(Exception):
    __slots__ = ()


def claim_streaming_multipart_body(scope: Scope) -> None:
    scope[_STREAMING_MULTIPART_OWNER_SCOPE_KEY] = True


class RequestBodyGuardMiddleware:
    def __init__(self, app: ASGIApp, *, policy: RequestBodyPolicy) -> None:
        self.app = app
        self._policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        is_multipart = is_multipart_media_type(request.headers.get("content-type"))
        maximum_bytes = self._maximum_bytes(scope)
        declared_length = _parse_content_length(request.headers.get("content-length"))
        if not is_multipart and declared_length is not None and declared_length > maximum_bytes:
            await self._send_violation(
                scope,
                receive,
                send,
                request,
                _payload_too_large_violation(),
            )
            return
        deadline = time.monotonic() + self._policy.read_deadline_seconds
        received_bytes = 0
        violation: _BodyViolation | None = None
        response_forwarded = False

        async def guarded_receive() -> Message:
            nonlocal received_bytes, violation
            if violation is not None:
                raise _BodyViolationSignal
            if is_multipart:
                if scope.get(_STREAMING_MULTIPART_OWNER_SCOPE_KEY) is not True:
                    violation = _streaming_multipart_required_violation()
                    raise _BodyViolationSignal
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0.0:
                violation = _timeout_violation()
                raise _BodyViolationSignal
            try:
                async with asyncio.timeout(remaining_seconds):
                    message = await receive()
            except TimeoutError as exception:
                violation = _timeout_violation()
                raise _BodyViolationSignal from exception
            if is_multipart:
                return message
            if message.get("type") != "http.request":
                return message
            body = message.get("body", b"")
            if isinstance(body, bytes | bytearray):
                received_bytes += len(body)
            elif isinstance(body, memoryview):
                received_bytes += body.nbytes
            if received_bytes > maximum_bytes:
                violation = _payload_too_large_violation()
                raise _BodyViolationSignal
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_forwarded
            if violation is not None:
                return
            await send(message)
            if message.get("type") == "http.response.start":
                response_forwarded = True

        try:
            await self.app(scope, guarded_receive, guarded_send)
        except _BodyViolationSignal as exception:
            if violation is None:
                raise StateError(
                    "Request body violation signal had no violation state.",
                    operation=OPERATION,
                ) from exception
        if violation is None:
            return
        if response_forwarded:
            invariant_error = StateError(
                "Request body violation occurred after the response started.",
                operation=OPERATION,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                invariant_error,
                message="Request body guard detected a response-start invariant violation.",
                operation=OPERATION,
            )
            raise invariant_error
        await self._send_violation(scope, receive, send, request, violation)

    def _maximum_bytes(self, scope: Scope) -> int:
        if is_public_inference_api_request_path(get_scope_path(scope)):
            return self._policy.openai_max_bytes
        return self._policy.native_max_bytes

    async def _send_violation(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        request: Request,
        violation: _BodyViolation,
    ) -> None:
        headers: dict[str, str] = {}
        http_version = scope.get("http_version")
        if isinstance(http_version, str) and http_version.startswith("1."):
            headers["Connection"] = "close"
        response = build_boundary_error_json_response_for_request(
            request,
            status_code=violation.status_code,
            message=violation.message,
            soai_code=violation.code,
            openai_code=violation.code,
            headers=headers,
        )
        await response(scope, receive, send)


def _parse_content_length(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized or not normalized.isdecimal():
        return None
    return int(normalized)


def _payload_too_large_violation() -> _BodyViolation:
    return _BodyViolation(
        status_code=413,
        code="payload_too_large",
        message="Request body exceeds the configured maximum size.",
    )


def _timeout_violation() -> _BodyViolation:
    return _BodyViolation(
        status_code=408,
        code="request_timeout",
        message="Request body was not received before the deadline.",
    )


def _streaming_multipart_required_violation() -> _BodyViolation:
    return _BodyViolation(
        status_code=415,
        code="streaming_multipart_required",
        message="Multipart request bodies must use the protected streaming upload path.",
    )
