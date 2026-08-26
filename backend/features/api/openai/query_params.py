"""SoAI - OpenAI route query parameter parsing [backend/features/api/openai/query_params.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from core.openai.pagination_coercion import (
    coerce_openai_int,
    coerce_openai_optional_int,
)
from core.validation.booleans import parse_bool_token_or_none
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.openai_error_responses import (
    build_openai_invalid_request_json_response,
)
from features.api.runtime.context import get_request_trace_id

__all__ = (
    "OpenAIListQueryParams",
    "parse_openai_bool_query",
    "parse_openai_int_query",
    "parse_openai_list_query_params",
)


@dataclass(frozen=True, slots=True)
class OpenAIListQueryParams:
    after: str | None
    before: str | None
    order: str
    limit: int


def parse_openai_bool_query(request: Request, key: str) -> bool:
    normalized = coerce_optional_trimmed_str(request.query_params.get(key))
    if normalized is None:
        return False
    parsed = parse_bool_token_or_none(normalized)
    return parsed if parsed is not None else False


def parse_openai_int_query(request: Request, key: str, default: int) -> int:
    normalized = coerce_optional_trimmed_str(request.query_params.get(key))
    if normalized is None:
        return int(default)
    return coerce_openai_int(normalized, default=default)


def parse_openai_list_query_params(
    request: Request,
    *,
    default_order: str,
    default_limit: int,
    strict_order: bool,
    strict_positive_limit: bool,
    max_limit: int | None = None,
) -> OpenAIListQueryParams | JSONResponse:
    order_or_error = _parse_order(
        request,
        default_order=default_order,
        strict_order=strict_order,
    )
    if isinstance(order_or_error, JSONResponse):
        return order_or_error
    limit_or_error = _parse_limit(
        request,
        default_limit=default_limit,
        strict_positive_limit=strict_positive_limit,
        max_limit=max_limit,
    )
    if isinstance(limit_or_error, JSONResponse):
        return limit_or_error
    return OpenAIListQueryParams(
        after=coerce_optional_trimmed_str(request.query_params.get("after")),
        before=coerce_optional_trimmed_str(request.query_params.get("before")),
        order=order_or_error,
        limit=limit_or_error,
    )


def _parse_order(
    request: Request,
    *,
    default_order: str,
    strict_order: bool,
) -> str | JSONResponse:
    normalized_default = default_order.strip().lower()
    order = coerce_optional_trimmed_str(request.query_params.get("order")) or normalized_default
    normalized_order = order.strip().lower()
    if normalized_order in {"asc", "desc"}:
        return normalized_order
    if not strict_order:
        return normalized_default
    return build_openai_invalid_request_json_response(
        message="order must be 'asc' or 'desc'.",
        param="order",
        trace_id=get_request_trace_id(request),
        status_code=400,
    )


def _parse_limit(
    request: Request,
    *,
    default_limit: int,
    strict_positive_limit: bool,
    max_limit: int | None,
) -> int | JSONResponse:
    limit_param = request.query_params.get("limit")
    limit = (
        coerce_openai_optional_int(limit_param) if limit_param is not None else int(default_limit)
    )
    if limit is None:
        if not strict_positive_limit:
            return int(default_limit)
        return build_openai_invalid_request_json_response(
            message="limit must be an integer.",
            param="limit",
            trace_id=get_request_trace_id(request),
            status_code=400,
        )
    if strict_positive_limit and limit <= 0:
        return build_openai_invalid_request_json_response(
            message="limit must be >= 1.",
            param="limit",
            trace_id=get_request_trace_id(request),
            status_code=400,
        )
    if max_limit is not None and limit > int(max_limit):
        return build_openai_invalid_request_json_response(
            message=f"limit must be <= {int(max_limit)}.",
            param="limit",
            trace_id=get_request_trace_id(request),
            status_code=400,
        )
    return limit
