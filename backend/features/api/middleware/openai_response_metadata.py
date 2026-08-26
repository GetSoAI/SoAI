"""SoAI - OpenAI-compatible response metadata headers [backend/features/api/middleware/openai_response_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.runtime.soai_identifiers import create_request_id
from core.runtime.state_access import read_state_value
from core.system_api.request_paths import (
    get_scope_path,
    is_anthropic_api_request_path,
    is_openai_compatibility_request_path,
)
from core.timing.monotonic import monotonic_ms
from features.api.runtime.openai_request_state import resolve_request_trace_id_optional

__all__ = (
    "OPENAI_PROCESSING_MS_HEADER_NAME",
    "OPENAI_REQUEST_ID_HEADER_NAME",
    "OPENAI_VERSION_HEADER_NAME",
    "OpenAIResponseMetadataMiddleware",
    "apply_anthropic_response_metadata_headers",
    "apply_openai_response_metadata_headers",
    "initialize_openai_response_metadata",
)

OPENAI_PROCESSING_MS_HEADER_NAME = "openai-processing-ms"
OPENAI_REQUEST_ID_HEADER_NAME = "x-request-id"
OPENAI_VERSION_HEADER_NAME = "openai-version"
OPENAI_API_VERSION = "2020-10-01"
ANTHROPIC_REQUEST_ID_HEADER_NAME = "request-id"
_OPENAI_RESPONSE_METADATA_STATE_KEY = "soai_openai_response_metadata"


@dataclass(frozen=True, slots=True)
class OpenAIResponseMetadata:
    started_at_monotonic_ms: int
    fallback_request_id: str


def initialize_openai_response_metadata(scope: Scope) -> OpenAIResponseMetadata:
    request_state = Request(scope).state
    existing = read_state_value(
        request_state,
        _OPENAI_RESPONSE_METADATA_STATE_KEY,
        OpenAIResponseMetadata,
    )
    if existing is not None:
        return existing
    metadata = OpenAIResponseMetadata(
        started_at_monotonic_ms=monotonic_ms(),
        fallback_request_id=create_request_id(prefix="openai"),
    )
    request_state.soai_openai_response_metadata = metadata
    return metadata


def _resolve_request_id(
    scope: Scope,
    headers: MutableHeaders,
    metadata: OpenAIResponseMetadata,
) -> str:
    trace_id = resolve_request_trace_id_optional(Request(scope))
    if trace_id is not None:
        return trace_id
    operation_id = headers.get("X-SoAI-Operation-Id")
    if operation_id is not None and operation_id.strip():
        return operation_id.strip()
    return metadata.fallback_request_id


def apply_openai_response_metadata_headers(
    scope: Scope,
    headers: MutableHeaders,
) -> None:
    metadata = initialize_openai_response_metadata(scope)
    elapsed_ms = max(0, monotonic_ms() - metadata.started_at_monotonic_ms)
    headers[OPENAI_REQUEST_ID_HEADER_NAME] = _resolve_request_id(scope, headers, metadata)
    headers[OPENAI_VERSION_HEADER_NAME] = OPENAI_API_VERSION
    headers[OPENAI_PROCESSING_MS_HEADER_NAME] = str(elapsed_ms)


def apply_anthropic_response_metadata_headers(
    scope: Scope,
    headers: MutableHeaders,
) -> None:
    metadata = initialize_openai_response_metadata(scope)
    headers[ANTHROPIC_REQUEST_ID_HEADER_NAME] = _resolve_request_id(scope, headers, metadata)


class OpenAIResponseMetadataMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = get_scope_path(scope)
        if scope.get("type") != "http" or not is_openai_compatibility_request_path(path):
            await self.app(scope, receive, send)
            return
        initialize_openai_response_metadata(scope)

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                if is_anthropic_api_request_path(path):
                    apply_anthropic_response_metadata_headers(scope, headers)
                else:
                    apply_openai_response_metadata_headers(scope, headers)
            await send(message)

        await self.app(scope, receive, send_wrapper)
