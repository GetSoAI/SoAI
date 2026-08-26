"""SoAI - Bounded WebUI password mutation orchestration [backend/features/api/routes/webui/user_password_changes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from fastapi import Request

from core.auth.jwt_claims import AccessTokenRecord
from core.users.identity_mutation_contract import (
    IDENTITY_MUTATION_DEADLINE_MS,
    IDENTITY_MUTATION_SERVER_HORIZON_MS,
)
from core.users.identity_mutation_records import IdentityMutationBinding
from core.users.password_change import PasswordChangeTransaction
from core.users.user_id import require_strict_user_id
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
from features.api.routes.webui.password_change_transaction_execution import (
    execute_password_change_transaction,
)
from features.api.routes.webui.session_successor_credentials import (
    PreparedSessionSuccessor,
)
from features.api.routes.webui.user_mutation_responses import (
    prepare_identity_mutation_response,
    raise_identity_mutation_failure,
    record_identity_mutation_failure,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser
from features.api.schemas.users import UserPasswordUpdate


async def change_webui_user_password(
    *,
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    payload: UserPasswordUpdate,
    target_user_id: int | None,
) -> IdentityMutationOutcome:
    deadline_monotonic = time.monotonic() + IDENTITY_MUTATION_DEADLINE_MS / 1000
    recovery_horizon_at_ms = int(time.time() * 1000) + IDENTITY_MUTATION_SERVER_HORIZON_MS
    actor_user_id = require_strict_user_id(current_user.get("id"))
    resolved_target_user_id = actor_user_id if target_user_id is None else target_user_id
    binding = IdentityMutationBinding(
        actor_user_id=actor_user_id,
        operation_id=payload.operation_id,
        operation_type="password_change",
        target_user_id=resolved_target_user_id,
        requested_username=None,
    )
    password_request = IdentityMutationRequest(
        binding,
        payload.current_password,
        deadline_monotonic,
        None,
    )
    async with verified_identity_mutation(
        request, api_context, password_request
    ) as password_verification:
        if isinstance(password_verification, IdentityMutationOutcome):
            return password_verification
        participants: VerifiedIdentityMutationParticipants = password_verification
        actor_changed = actor_user_id == resolved_target_user_id
        remaining_seconds = deadline_monotonic - time.monotonic()
        if remaining_seconds <= 0:
            await record_identity_mutation_failure(
                api_context.dependencies.database_user_mutations,
                binding,
                "identity_mutation_deadline_exceeded",
            )
            return await build_identity_mutation_replay(
                request=request,
                api_context=api_context,
                binding=binding,
            )
        new_hashed_password = await api_context.dependencies.login_password_service.hash_password(
            payload.new_password,
            timeout_sec=remaining_seconds,
        )
        prepared_successor: PreparedSessionSuccessor | None = None
        if actor_changed:
            password_successor_result = await prepare_identity_mutation_successor(
                request,
                api_context,
                IdentityMutationSuccessorRequest(
                    username=participants.actor.username,
                    password_revision=participants.actor.password_revision + 1,
                    binding=binding,
                    recovery_horizon_at_ms=recovery_horizon_at_ms,
                    source_jti=participants.source_jti,
                ),
            )
            if isinstance(password_successor_result, IdentityMutationOutcome):
                return password_successor_result
            prepared_successor = password_successor_result
        replacement_token: AccessTokenRecord | None = (
            prepared_successor.token if prepared_successor is not None else None
        )
        transaction = PasswordChangeTransaction(
            binding=binding,
            actor=participants.actor,
            target=participants.target,
            source_jti=participants.source_jti,
            new_hashed_password=new_hashed_password,
            deadline_monotonic=deadline_monotonic,
            recovery_horizon_at_ms=recovery_horizon_at_ms,
            successor=replacement_token,
            source_descriptor=(
                prepared_successor.descriptor if prepared_successor is not None else None
            ),
        )
        response_without_rotation = prepare_identity_mutation_response(
            request=request,
            api_context=api_context,
            operation_id=payload.operation_id,
            user=participants.target_record,
            replacement_token=None,
            source_csrf_token=None,
        )
        result, replacement_token = await execute_password_change_transaction(
            api_context=api_context,
            transaction=transaction,
            successor_allocator=(
                prepared_successor.allocator if prepared_successor is not None else None
            ),
            actor_user_id=actor_user_id,
            successor_username=participants.actor.username,
            successor_password_revision=participants.actor.password_revision + 1,
            operation_id=payload.operation_id,
        )
        response_with_rotation = prepare_identity_mutation_response(
            request=request,
            api_context=api_context,
            operation_id=payload.operation_id,
            user=participants.target_record,
            replacement_token=replacement_token,
            source_csrf_token=(
                prepared_successor.csrf_token if prepared_successor is not None else None
            ),
        )
        if result.record.status == "failed" and result.record.error_code is not None:
            raise_identity_mutation_failure(result.record.error_code, payload.operation_id)
        if not result.committed_now:
            return await build_identity_mutation_replay(
                request=request,
                api_context=api_context,
                binding=binding,
            )
        response_user = result.user if result.user is not None else participants.target_record
        should_set_cookie = actor_changed and participants.source_jti in result.revoked_jtis
        log_identity_mutation_audit_noncritical(
            request,
            action="CHANGE_OWN_PASSWORD" if actor_changed else "CHANGE_USER_PASSWORD",
            target_username=participants.target.username,
            target_user_id=resolved_target_user_id,
            actor_user_id=actor_user_id,
        )
        return IdentityMutationOutcome(
            payload.operation_id,
            response_user,
            actor_changed,
            response_with_rotation if should_set_cookie else response_without_rotation,
            replacement_token if should_set_cookie else None,
            (
                prepared_successor.csrf_token
                if should_set_cookie and prepared_successor is not None
                else None
            ),
        )


__all__ = ("change_webui_user_password",)
