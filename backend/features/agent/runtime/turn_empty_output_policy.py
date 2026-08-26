"""SoAI - Agent turn empty-output retry predicates [backend/features/agent/runtime/turn_empty_output_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from features.agent.runtime.turn_iteration_policy_types import (
        TurnIterationPolicyConfig,
        TurnIterationPolicyState,
    )

__all__ = (
    "is_empty_assistant_output",
    "should_retry_empty_output",
    "should_retry_empty_output_silently",
)


def is_empty_assistant_output(assistant_text: str | None) -> bool:
    if assistant_text is None:
        return True
    return not assistant_text.strip()


def should_retry_empty_output_silently(
    *,
    config: TurnIterationPolicyConfig,
    state: TurnIterationPolicyState,
    assistant_text: str | None,
) -> bool:
    if config.max_empty_output_silent_retries <= 0:
        return False
    if state.empty_output_silent_retries >= config.max_empty_output_silent_retries:
        return False
    return is_empty_assistant_output(assistant_text)


def should_retry_empty_output(
    *,
    config: TurnIterationPolicyConfig,
    state: TurnIterationPolicyState,
    assistant_text: str | None,
) -> bool:
    if config.max_empty_output_retries <= 0:
        return False
    if state.empty_output_retries >= config.max_empty_output_retries:
        return False
    return is_empty_assistant_output(assistant_text)
