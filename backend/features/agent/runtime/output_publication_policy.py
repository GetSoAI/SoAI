"""SoAI - Agent turn output publication policy [backend/features/agent/runtime/output_publication_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)

__all__ = (
    "resolve_next_output_publication_mode",
    "turn_requires_validated_publication",
)


def turn_requires_validated_publication(mode: AgentOutputPublicationMode) -> bool:
    return mode is AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH


def resolve_next_output_publication_mode(
    *,
    current_mode: AgentOutputPublicationMode,
    requested_mode: AgentOutputPublicationMode,
) -> AgentOutputPublicationMode:
    if turn_requires_validated_publication(current_mode):
        return AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH
    return requested_mode
