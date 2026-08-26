"""SoAI - Runtime configuration reload parsing and restart assessment [backend/app/runtime_config_reload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.runtime_http_client_settings import normalize_http_client_section
from core.errors.exceptions import ValidationError
from features.api.lifecycle.rate_limiting_config import (
    RateLimitConfiguration,
    build_rate_limit_configuration_from_mapping,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "append_reload_error",
    "assess_routing_only_reload",
    "build_rate_limit_configuration_from_dict",
)


def append_reload_error(existing: str | None, new_error: str) -> str:
    if existing:
        return f"{existing}; {new_error}"
    return new_error


def detect_http_client_setting_changes(
    *,
    routing_section: JSONDict,
    startup_http_client_limits: dict[str, JSONValue] | None,
    startup_http_client_timeouts: dict[str, JSONValue] | None,
) -> str | None:
    new_limits = normalize_http_client_section(routing_section.get("HTTP_CLIENT_LIMITS"))
    new_timeouts = normalize_http_client_section(routing_section.get("HTTP_CLIENT_TIMEOUTS"))
    limits_changed = startup_http_client_limits != new_limits
    timeouts_changed = startup_http_client_timeouts != new_timeouts
    if not limits_changed and not timeouts_changed:
        return None
    return "MODELS.ROUTING HTTP client settings changed (requires restart)."


def assess_routing_only_reload(
    *,
    config_dict: JSONDict,
    startup_http_client_limits: dict[str, JSONValue] | None,
    startup_http_client_timeouts: dict[str, JSONValue] | None,
) -> tuple[str | None, str | None]:
    models_section = config_dict.get("MODELS")
    if not isinstance(models_section, dict):
        return (None, None)
    routing_section = models_section.get("ROUTING")
    if routing_section is None:
        return (None, None)
    if not isinstance(routing_section, dict):
        return ("MODELS.ROUTING must be a mapping.", None)
    restart_reason = detect_http_client_setting_changes(
        routing_section=routing_section,
        startup_http_client_limits=startup_http_client_limits,
        startup_http_client_timeouts=startup_http_client_timeouts,
    )
    return (None, restart_reason)


def _disabled_rate_limit_configuration() -> RateLimitConfiguration:
    return RateLimitConfiguration(
        enabled=False,
        default_limit=None,
        stream_limit=None,
        routers={},
    )


def build_rate_limit_configuration_from_dict(config_dict: JSONDict) -> RateLimitConfiguration:
    api_value = config_dict.get("API")
    if api_value is None:
        return _disabled_rate_limit_configuration()
    if not isinstance(api_value, dict):
        raise ValidationError("API must be a mapping.")
    openai_api_value = api_value.get("OPENAI")
    if openai_api_value is None:
        return _disabled_rate_limit_configuration()
    if not isinstance(openai_api_value, dict):
        raise ValidationError("API.OPENAI must be a mapping.")
    api_rate_limiting_value = openai_api_value.get("RATE_LIMITING")
    if api_rate_limiting_value is None:
        return _disabled_rate_limit_configuration()
    if not isinstance(api_rate_limiting_value, dict):
        raise ValidationError("API.OPENAI.RATE_LIMITING must be a mapping.")
    return build_rate_limit_configuration_from_mapping(api_rate_limiting_value)
