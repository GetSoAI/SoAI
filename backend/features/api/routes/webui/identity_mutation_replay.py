"""SoAI - Durable identity mutation response recovery [backend/features/api/routes/webui/identity_mutation_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response

from core.auth.jwt_claims import AccessTokenRecord
from core.errors.exceptions import SecurityError
from core.types.json import JSONDict
from core.users.identity_mutation_records import IdentityMutationBinding
from features.api.routes.webui.auth_session_rotation import recover_request_session_rotation
from features.api.routes.webui.user_mutation_responses import (
    prepare_identity_mutation_response,
    raise_identity_mutation_failure,
    record_identity_mutation_failure,
)
from features.api.runtime.auth_request_state import require_request_auth_method
from features.api.runtime.context import ApiContext


@dataclass(frozen=True, slots=True)
class IdentityMutationOutcome:
    operation_id: str
    user: JSONDict
    actor_changed: bool
    response: Response
    replacement_token: AccessTokenRecord | None
    source_csrf_token: str | None


async def build_identity_mutation_replay(
    *,
    request: Request,
    api_context: ApiContext,
    binding: IdentityMutationBinding,
) -> IdentityMutationOutcome:
    current_target = await api_context.dependencies.database_users.get_human_user_by_id(
        binding.target_user_id
    )
    if current_target is None:
        raise_identity_mutation_failure("user_state_conflict", binding.operation_id)
    actor_changed = binding.actor_user_id == binding.target_user_id
    if actor_changed:
        recovered = await recover_request_session_rotation(
            request,
            api_context,
            expected_operation_id=binding.operation_id,
        )
        if recovered is not None:
            response = prepare_identity_mutation_response(
                request=request,
                api_context=api_context,
                operation_id=binding.operation_id,
                user=recovered.user,
                replacement_token=recovered.token_record,
                source_csrf_token=recovered.csrf_token,
            )
            return IdentityMutationOutcome(
                binding.operation_id,
                recovered.user,
                True,
                response,
                recovered.token_record,
                recovered.csrf_token,
            )
        if require_request_auth_method(request) == "jwt_cookie_rotation_recovery":
            raise SecurityError("Session rotation is no longer recoverable.")
    response = prepare_identity_mutation_response(
        request=request,
        api_context=api_context,
        operation_id=binding.operation_id,
        user=current_target,
        replacement_token=None,
        source_csrf_token=None,
    )
    return IdentityMutationOutcome(
        binding.operation_id,
        current_target,
        actor_changed,
        response,
        None,
        None,
    )


async def fail_identity_mutation_and_replay(
    *,
    request: Request,
    api_context: ApiContext,
    binding: IdentityMutationBinding,
    error_code: str,
) -> IdentityMutationOutcome:
    await record_identity_mutation_failure(
        api_context.dependencies.database_user_mutations,
        binding,
        error_code,
    )
    return await build_identity_mutation_replay(
        request=request,
        api_context=api_context,
        binding=binding,
    )


__all__ = (
    "IdentityMutationOutcome",
    "build_identity_mutation_replay",
    "fail_identity_mutation_and_replay",
)
