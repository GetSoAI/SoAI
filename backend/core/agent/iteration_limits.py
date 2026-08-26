"""SoAI - Agent max-iteration limit policy [backend/core/agent/iteration_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = (
    "DEFAULT_AGENT_MAX_ITERATIONS",
    "MAX_AGENT_MAX_ITERATIONS",
    "require_agent_max_iterations",
    "resolve_agent_max_iterations",
)

DEFAULT_AGENT_MAX_ITERATIONS = 1_000_000
MAX_AGENT_MAX_ITERATIONS = 1_000_000_000


def require_agent_max_iterations(value: JSONValue) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("model_settings.agent.max_iterations must be an integer.")
    if value < 1:
        raise ValidationError("model_settings.agent.max_iterations must be >= 1.")
    if value > MAX_AGENT_MAX_ITERATIONS:
        raise ValidationError(
            f"model_settings.agent.max_iterations must be <= {MAX_AGENT_MAX_ITERATIONS}.",
        )
    return int(value)


def resolve_agent_max_iterations(agent_settings: Mapping[str, JSONValue]) -> int:
    if "max_iterations" not in agent_settings:
        return DEFAULT_AGENT_MAX_ITERATIONS
    return require_agent_max_iterations(agent_settings["max_iterations"])
