"""SoAI - Rate limiting configuration logic for API lifecycle [backend/features/api/lifecycle/rate_limiting_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import formatdate
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from starlette.responses import Response

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from core.timing.epoch import epoch_seconds
from core.types.json import is_json_value
from core.types.json_value import coerce_json_dict
from core.validation.boolean_coercion import coerce_bool_with_default
from features.api.rate_limiting.rate_limit_evaluator import (
    ApiRateLimitExceeded,
    RateLimitBreach,
)
from features.api.rate_limiting.rate_limit_overrides import normalize_rate_limit_value
from features.api.rate_limiting.rate_limit_resolution import (
    build_resolved_rate_limit_config,
    build_router_limit_targets,
    rate_limit_config_signature,
    validate_rate_limit_config_keys,
)
from features.api.rate_limiting.runtime_state import ensure_rate_limit_runtime_state
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
    build_coerced_json_error_response,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import get_request_trace_id

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue
    from core.types.json import JSONValue

__all__ = (
    "RateLimitConfiguration",
    "apply_rate_limiting",
    "build_rate_limit_configuration",
    "build_rate_limit_configuration_from_mapping",
    "build_rate_limit_configuration_from_values",
    "handle_rate_limit_exceeded",
)

LOGGER_NAME = "SoAI.features.api.rate_limiting_config"


@dataclass(frozen=True, slots=True)
class RateLimitConfiguration:
    enabled: bool
    default_limit: str | None
    stream_limit: str | None
    routers: Mapping[str, JSONValue]


def build_rate_limit_configuration_from_values(
    *,
    enabled: bool,
    default_limit_raw: JSONValue,
    stream_limit_raw: JSONValue,
    routers_raw: JSONValue,
) -> RateLimitConfiguration:
    default_limit = normalize_rate_limit_value(
        default_limit_raw,
        field_label="API.OPENAI.RATE_LIMITING.DEFAULT_LIMIT",
    )
    stream_limit = normalize_rate_limit_value(
        stream_limit_raw,
        field_label="API.OPENAI.RATE_LIMITING.STREAM_LIMIT",
    )
    resolved_routers = coerce_json_dict(routers_raw)
    if resolved_routers is None:
        raise ValidationError("API.OPENAI.RATE_LIMITING.ROUTERS must be a mapping.")
    return RateLimitConfiguration(
        enabled=enabled,
        default_limit=default_limit,
        stream_limit=stream_limit,
        routers=resolved_routers,
    )


def build_rate_limit_configuration_from_mapping(
    rate_limit_config: Mapping[str, JSONValue],
) -> RateLimitConfiguration:
    validate_rate_limit_config_keys(rate_limit_config)
    enabled = coerce_bool_with_default(
        rate_limit_config.get("ENABLED"),
        default=False,
        strict=False,
    )
    return build_rate_limit_configuration_from_values(
        enabled=enabled,
        default_limit_raw=rate_limit_config.get("DEFAULT_LIMIT"),
        stream_limit_raw=rate_limit_config.get("STREAM_LIMIT"),
        routers_raw=rate_limit_config.get("ROUTERS", {}),
    )


def _require_rate_limit_json_value(value: ConfigValue | None, field_label: str) -> JSONValue:
    if is_json_value(value):
        return value
    raise ValidationError(f"{field_label} must be JSON-compatible.")


def build_rate_limit_configuration(
    config_obj: ConfigProtocol,
) -> RateLimitConfiguration:
    rate_limit_config_raw = config_obj.get("API.OPENAI.RATE_LIMITING")
    if rate_limit_config_raw is not None:
        rate_limit_config = _require_rate_limit_json_value(
            rate_limit_config_raw,
            "API.OPENAI.RATE_LIMITING",
        )
        if not isinstance(rate_limit_config, Mapping):
            raise ValidationError("API.OPENAI.RATE_LIMITING must be a mapping.")
        validate_rate_limit_config_keys(rate_limit_config)
    enabled = config_obj.get_bool("API.OPENAI.RATE_LIMITING.ENABLED")
    default_limit_raw = config_obj.get("API.OPENAI.RATE_LIMITING.DEFAULT_LIMIT")
    stream_limit_raw = config_obj.get("API.OPENAI.RATE_LIMITING.STREAM_LIMIT")
    routers_raw = config_obj.get("API.OPENAI.RATE_LIMITING.ROUTERS", {})
    return build_rate_limit_configuration_from_values(
        enabled=enabled,
        default_limit_raw=_require_rate_limit_json_value(
            default_limit_raw,
            "API.OPENAI.RATE_LIMITING.DEFAULT_LIMIT",
        ),
        stream_limit_raw=_require_rate_limit_json_value(
            stream_limit_raw,
            "API.OPENAI.RATE_LIMITING.STREAM_LIMIT",
        ),
        routers_raw=_require_rate_limit_json_value(
            routers_raw,
            "API.OPENAI.RATE_LIMITING.ROUTERS",
        ),
    )


def apply_rate_limiting(
    app: FastAPI,
    request_rate_limiter: MovingWindowRateLimiter,
    config: RateLimitConfiguration,
    already_initialized: bool,
) -> None:
    runtime_state = ensure_rate_limit_runtime_state(app.state, request_rate_limiter)
    existing_resolved = runtime_state.get_config()
    previous_signature = existing_resolved.signature if existing_resolved is not None else None
    if config.enabled:
        rate_limit_config_dict: dict[str, JSONValue] = {
            "DEFAULT_LIMIT": config.default_limit,
            "STREAM_LIMIT": config.stream_limit,
            "ROUTERS": config.routers,
        }
        signature = rate_limit_config_signature(rate_limit_config_dict)
        resolved = None
        if previous_signature != signature:
            try:
                routers_holder = app.state.api_routers
            except AttributeError:
                routers_holder = None
            if not isinstance(routers_holder, ApiRouters):
                raise StateError(
                    "api_routers must be initialized before configuring rate limiting.",
                )
            router_targets = build_router_limit_targets(routers_holder)
            resolved = build_resolved_rate_limit_config(rate_limit_config_dict, router_targets)
        if not already_initialized:
            get_logger(LOGGER_NAME).info("API Rate Limiting is ENABLED.")
        if resolved is not None:
            runtime_state.replace_config(resolved, reset_counters=True)
    else:
        if not already_initialized:
            get_logger(LOGGER_NAME).info("API Rate Limiting is DISABLED by configuration.")
        if previous_signature is not None:
            runtime_state.replace_config(None, reset_counters=True)
        else:
            runtime_state.replace_config(None, reset_counters=False)


def handle_rate_limit_exceeded(request: Request, exception: Exception) -> Response:
    trace_id = get_request_trace_id(request)
    if not isinstance(exception, ApiRateLimitExceeded):
        return build_coerced_json_error_response(
            exception,
            trace_id=trace_id,
            operation="api_lifecycle.rate_limit_exceeded",
        )
    breach = exception.breach
    response = build_boundary_error_json_response_for_request(
        request,
        status_code=429,
        message="Rate limit exceeded.",
        soai_code="rate_limit_exceeded",
        openai_code=None,
        details={"limit": breach.rule.label},
        trace_id=trace_id,
    )
    _inject_rate_limit_headers(response, breach=breach)
    return response


def _inject_rate_limit_headers(
    response: Response,
    *,
    breach: RateLimitBreach,
) -> None:
    reset_at = int(breach.stats.reset_epoch_seconds)
    response.headers["X-RateLimit-Limit"] = str(breach.stats.limit)
    response.headers["X-RateLimit-Remaining"] = str(breach.stats.remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_at)
    now_seconds = int(epoch_seconds())
    retry_after_seconds = max(0, reset_at - now_seconds)
    response.headers["Retry-After"] = formatdate(
        now_seconds + retry_after_seconds,
        usegmt=True,
    )
