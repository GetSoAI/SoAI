"""SoAI - Required self-mutation session successor preparation [backend/features/api/routes/webui/identity_mutation_successor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from core.users.identity_mutation_records import IdentityMutationBinding
from features.api.routes.webui.identity_mutation_replay import (
    IdentityMutationOutcome,
    build_identity_mutation_replay,
    fail_identity_mutation_and_replay,
)
from features.api.routes.webui.identity_mutation_session_window import (
    verify_identity_mutation_session_window,
)
from features.api.routes.webui.session_successor_credentials import (
    PreparedSessionSuccessor,
    prepare_session_successor,
)
from features.api.runtime.context import ApiContext


@dataclass(frozen=True, slots=True)
class IdentityMutationSuccessorRequest:
    username: str
    password_revision: int
    binding: IdentityMutationBinding
    recovery_horizon_at_ms: int
    source_jti: str


async def prepare_identity_mutation_successor(
    request: Request,
    api_context: ApiContext,
    successor_request: IdentityMutationSuccessorRequest,
) -> PreparedSessionSuccessor | IdentityMutationOutcome:
    binding = successor_request.binding
    if await verify_identity_mutation_session_window(
        request,
        api_context,
        binding,
        successor_request.recovery_horizon_at_ms,
    ):
        return await build_identity_mutation_replay(
            request=request,
            api_context=api_context,
            binding=binding,
        )
    prepared = await prepare_session_successor(
        request,
        api_context,
        binding.operation_id,
        user_id=binding.actor_user_id,
        source_jti=successor_request.source_jti,
        username=successor_request.username,
        password_revision=successor_request.password_revision,
    )
    if prepared is not None:
        return prepared
    return await fail_identity_mutation_and_replay(
        request=request,
        api_context=api_context,
        binding=binding,
        error_code="user_state_conflict",
    )


__all__ = (
    "IdentityMutationSuccessorRequest",
    "prepare_identity_mutation_successor",
)
