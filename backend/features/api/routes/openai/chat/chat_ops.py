"""SoAI - OpenAI chat route operations [backend/features/api/routes/openai/chat/chat_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.orchestrator.routing_config import RoutingConfig
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.validation.numbers import coerce_float_from_json
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_effective_routing_config",
    "resolve_non_streaming_timeout",
    "resolve_non_streaming_timeout_from_request_json",
)


def resolve_non_streaming_timeout(
    routing_config: RoutingConfig,
    requested_timeout: float | None,
) -> float:
    if isinstance(requested_timeout, int | float) and not isinstance(requested_timeout, bool):
        normalized = float(requested_timeout)
        if normalized > 0:
            return normalized
    health_checks = routing_config.health_checks
    if isinstance(health_checks, Mapping):
        configured_timeout = health_checks.get("NON_STREAMING_TIMEOUT_SEC")
        if (
            isinstance(configured_timeout, int | float)
            and not isinstance(configured_timeout, bool)
            and configured_timeout > 0
        ):
            return float(configured_timeout)
    return float(LONG_REQUEST_TIMEOUT_SEC)


def get_effective_routing_config(api_context: OpenAIApiContextProtocol) -> RoutingConfig:
    return api_context.dependencies.orchestrator_lifecycle.routing_config


def resolve_non_streaming_timeout_from_request_json(
    request_json: JSONDict,
) -> float:
    requested_timeout = request_json.get("timeout")
    if not isinstance(requested_timeout, int | float) or isinstance(requested_timeout, bool):
        return 0.0
    normalized_timeout = coerce_float_from_json(requested_timeout, default=None)
    if normalized_timeout is None or normalized_timeout <= 0:
        return 0.0
    return normalized_timeout
