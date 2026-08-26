"""SoAI - Bounded username rename orchestration [backend/features/api/routes/webui/username_rename_orchestration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import replace

from fastapi import Request

from core.auth.jwt_claims import AccessTokenRecord
from core.auth.webui_sessions import WebuiSessionJtiCollisionError
from core.errors.exceptions import ApiError, ConflictError, StateError
from core.state.errors import DatabaseTimeoutError
from core.users.identity_mutation_contract import (
    IDENTITY_MUTATION_DEADLINE_MS,
    IDENTITY_MUTATION_SERVER_HORIZON_MS,
)
from core.users.identity_mutation_records import IdentityMutationBinding
from core.users.username_rename import (
    UsernameRenameDatabaseResult,
    UsernameRenameTransaction,
)
from features.api.routes.webui.identity_mutation_admission import (
    IdentityMutationRequest,
    VerifiedIdentityMutationParticipants,
    verified_identity_mutation,
)
from features.api.routes.webui.identity_mutation_audit import (
    log_identity_mutation_audit_noncritical,
)
from features.api.routes.webui.identity_mutation_replay import (
    IdentityMutationOutcome,
    build_identity_mutation_replay,
)
from features.api.routes.webui.identity_mutation_successor import (
    IdentityMutationSuccessorRequest,
    prepare_identity_mutation_successor,
)
from features.api.routes.webui.session_successor_credentials import (
    PreparedSessionSuccessor,
)
from features.api.routes.webui.user_mutation_responses import (
    prepare_identity_mutation_response,
    raise_identity_mutation_failure,
)
from features.api.runtime.context import ApiContext
from features.api.schemas.users import UsernameRenamePayload


async def rename_username(
    *,
    request: Request,
    api_context: ApiContext,
    actor_user_id: int,
    target_user_id: int,
    payload: UsernameRenamePayload,
) -> IdentityMutationOutcome:
    started_monotonic = time.monotonic()
    deadline_monotonic = started_monotonic + IDENTITY_MUTATION_DEADLINE_MS / 1000
    request_wall_ms = int(time.time() * 1000)
    recovery_horizon_at_ms = request_wall_ms + IDENTITY_MUTATION_SERVER_HORIZON_MS
    binding = IdentityMutationBinding(
        actor_user_id=actor_user_id,
        operation_id=payload.operation_id,
        operation_type="username_rename",
        target_user_id=target_user_id,
        requested_username=payload.new_username,
    )
    rename_request = IdentityMutationRequest(
        binding,
        payload.current_password,
        deadline_monotonic,
        payload.new_username,
    )
    async with verified_identity_mutation(
        request, api_context, rename_request
    ) as rename_verification:
        if isinstance(rename_verification, IdentityMutationOutcome):
            return rename_verification
        participants: VerifiedIdentityMutationParticipants = rename_verification
        is_self = actor_user_id == target_user_id
        prepared_successor: PreparedSessionSuccessor | None = None
        if is_self:
            rename_successor_result = await prepare_identity_mutation_successor(
                request,
                api_context,
                IdentityMutationSuccessorRequest(
                    username=payload.new_username,
                    password_revision=participants.actor.password_revision,
                    binding=binding,
                    recovery_horizon_at_ms=recovery_horizon_at_ms,
                    source_jti=participants.source_jti,
                ),
            )
            if isinstance(rename_successor_result, IdentityMutationOutcome):
                return rename_successor_result
            prepared_successor = rename_successor_result
        replacement_token: AccessTokenRecord | None = (
            prepared_successor.token if prepared_successor is not None else None
        )
        transaction = UsernameRenameTransaction(
            binding=binding,
            actor=participants.actor,
            target=participants.target,
            source_jti=participants.source_jti,
            deadline_monotonic=deadline_monotonic,
            recovery_horizon_at_ms=recovery_horizon_at_ms,
            successor=replacement_token,
            source_descriptor=(
                prepared_successor.descriptor if prepared_successor is not None else None
            ),
        )
        response_user = dict(participants.target_record)
        response_user["username"] = payload.new_username
        response_user["identity_revision"] = participants.target.identity_revision + 1
        result: UsernameRenameDatabaseResult | None = None
        while result is None:
            try:
                result = await api_context.dependencies.database_user_mutations.rename_username(
                    transaction
                )
            except WebuiSessionJtiCollisionError as exception:
                if prepared_successor is None:
                    raise StateError(
                        "A non-rotating username mutation collided with a session."
                    ) from exception
                replacement_token = await prepared_successor.allocator.create(
                    user_id=actor_user_id,
                    username=payload.new_username,
                    password_revision=participants.actor.password_revision,
                )
                transaction = replace(transaction, successor=replacement_token)
            except ConflictError:
                raise_identity_mutation_failure(
                    "operation_id_conflict",
                    payload.operation_id,
                )
            except DatabaseTimeoutError as exception:
                raise ApiError(
                    "Identity mutation result is unknown.",
                    code="identity_mutation_result_unknown",
                    http_status=503,
                    details={"operation_id": payload.operation_id},
                    cause=exception,
                ) from exception
        result_record = result.record
        if result_record.status == "failed" and result_record.error_code is not None:
            raise_identity_mutation_failure(
                result_record.error_code,
                operation_id=payload.operation_id,
            )
        if not result.committed_now:
            return await build_identity_mutation_replay(
                request=request,
                api_context=api_context,
                binding=binding,
            )
        should_set_cookie = (
            is_self
            and replacement_token is not None
            and participants.source_jti in result.revoked_jtis
        )
        response = prepare_identity_mutation_response(
            request=request,
            api_context=api_context,
            operation_id=payload.operation_id,
            user=response_user,
            replacement_token=replacement_token if should_set_cookie else None,
            source_csrf_token=(
                prepared_successor.csrf_token
                if should_set_cookie and prepared_successor is not None
                else None
            ),
        )
        log_identity_mutation_audit_noncritical(
            request,
            action="RENAME_OWN_USERNAME" if is_self else "RENAME_USER_USERNAME",
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            target_username=payload.new_username,
            previous_username=participants.target.username,
        )
        return IdentityMutationOutcome(
            operation_id=payload.operation_id,
            user=response_user,
            actor_changed=is_self,
            response=response,
            replacement_token=replacement_token if should_set_cookie else None,
            source_csrf_token=(
                prepared_successor.csrf_token
                if should_set_cookie and prepared_successor is not None
                else None
            ),
        )


__all__ = ("rename_username",)
