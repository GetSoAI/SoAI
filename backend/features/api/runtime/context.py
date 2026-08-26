"""SoAI - Request context and runtime helpers for API [backend/features/api/runtime/context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from fastapi import Request, status
from starlette.applications import Starlette
from starlette.requests import HTTPConnection

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ApiError, StateError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.openai.modalities import (
    collect_message_modalities,
    get_openai_capability_taxonomy,
)
from core.runtime.protocols import (
    ConnectionProtocol,
    RequestOwnershipContextProtocol,
    RequestProtocol,
)
from core.runtime.proxy_headers import extract_real_client_ip
from core.runtime.request_context import RequestContext
from core.runtime.request_trace_id import get_request_trace_id
from core.types.json import JSONDict
from features.api.runtime.container.types import ApiDependencies
from features.api.runtime.user_coercion import coerce_current_user
from features.api.runtime.user_types import CurrentUser

__all__ = (
    "ApiContext",
    "attach_api_dependencies",
    "collect_message_modalities",
    "get_current_user_optional",
    "get_openai_capability_taxonomy",
    "get_remote_address",
    "get_request_trace_id",
    "log_api_exception",
    "raise_api_error",
    "require_request_context_instance",
    "require_request_context",
    "resolve_api_context",
    "resolve_api_dependencies",
)


@dataclass(frozen=True, slots=True)
class ApiContext:
    request: ConnectionProtocol
    dependencies: ApiDependencies


def require_request_context(
    request: ConnectionProtocol,
) -> RequestOwnershipContextProtocol:
    try:
        context: RequestOwnershipContextProtocol = request.state.context
    except AttributeError as exception:
        raise StateError("Request context is not initialized.") from exception
    if context is None:
        raise StateError("Request context is not initialized.")
    if isinstance(context, RequestContext):
        return context
    try:
        trace_id_value = context.trace_id
    except AttributeError as exception:
        raise StateError("Request context is missing a trace ID.") from exception
    if not isinstance(trace_id_value, str) or not trace_id_value.strip():
        raise StateError("Request context is missing a trace ID.")
    return context


def require_request_context_instance(request: ConnectionProtocol) -> RequestContext:
    context = require_request_context(request)
    if isinstance(context, RequestContext):
        return context
    raise StateError("Full request context is not initialized.")


def attach_api_dependencies(app: Starlette, api_dependencies: ApiDependencies) -> None:
    if not isinstance(api_dependencies, ApiDependencies):
        raise ValidationError("API dependencies must be an ApiDependencies instance.")
    app.state.api_dependencies = api_dependencies


def resolve_api_dependencies(request: HTTPConnection) -> ApiDependencies:
    try:
        api_dependencies = request.app.state.api_dependencies
    except AttributeError:
        raise_api_error(
            request,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorType.SERVICE_UNAVAILABLE.value,
            "API dependencies are not configured.",
        )
    if not isinstance(api_dependencies, ApiDependencies):
        raise_api_error(
            request,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorType.SERVICE_UNAVAILABLE.value,
            "API dependencies are not configured.",
        )
    return api_dependencies


def resolve_api_context(request: HTTPConnection) -> ApiContext:
    api_dependencies = resolve_api_dependencies(request)
    try:
        existing_context = request.state.api_context
    except AttributeError:
        existing_context = None
    if isinstance(existing_context, ApiContext):
        if existing_context.dependencies is api_dependencies:
            return existing_context
    api_context = ApiContext(request=request, dependencies=api_dependencies)
    request.state.api_context = api_context
    return api_context


async def get_current_user_optional(request: Request) -> CurrentUser | None:
    try:
        user_value = request.state.user
    except AttributeError:
        user_value = None
    if user_value is None:
        return None
    return coerce_current_user(user_value)


def get_remote_address(request: RequestProtocol) -> str:
    real_ip = extract_real_client_ip(request)
    if real_ip:
        return real_ip
    client = request.client
    host = client.host if client else None
    return host or "unknown"


def raise_api_error(
    request: ConnectionProtocol,
    status_code: int,
    error_type: str,
    message: str,
    *,
    extra: JSONDict | None = None,
    headers: dict[str, str] | None = None,
) -> NoReturn:
    trace_id = get_request_trace_id(request)
    raise ApiError(
        message,
        code=error_type,
        http_status=status_code,
        trace_id=trace_id,
        details=extra,
        headers=headers,
    )


def log_api_exception(
    logger: LoggerProtocol,
    request: Request,
    exception: BaseException,
    *,
    message: str,
    operation: str,
    level: str = "error",
) -> str | None:
    trace_id = get_request_trace_id(request)
    log_exception(
        logger,
        exception,
        message=message,
        trace_id=trace_id,
        operation=operation,
        level=level,
    )
    return trace_id
