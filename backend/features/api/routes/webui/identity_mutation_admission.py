"""SoAI - Identity mutation admission and locked actor proof [backend/features/api/routes/webui/identity_mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import Request

from core.auth.auth_failure_buckets import build_webui_login_failure_buckets
from core.auth.jwt_tokens import require_request_session_jti
from core.errors.exceptions import ApiError
from core.types.json import JSONDict
from core.users.identity_mutation_records import IdentityMutationBinding
from core.users.username_rename import (
    UserIdentitySnapshot,
    user_identity_snapshot_from_record,
)
from features.api.routes.webui.identity_mutation_password_proof import (
    verify_identity_mutation_actor_password,
)
from features.api.routes.webui.identity_mutation_replay import (
    IdentityMutationOutcome,
    build_identity_mutation_replay,
    fail_identity_mutation_and_replay,
)
from features.api.routes.webui.identity_mutation_throttling import (
    enforce_identity_mutation_attempt_limit,
)
from features.api.routes.webui.user_mutation_responses import (
    has_terminal_identity_mutation,
)
from features.api.routes.webui.webui_auth_resource_locking import (
    lock_webui_auth_resources,
    session_mutation_resource,
    username_auth_resource,
)
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.context import ApiContext


@dataclass(frozen=True, slots=True)
class IdentityMutationAdmission:
    binding: IdentityMutationBinding
    initial_actor: UserIdentitySnapshot
    initial_target: UserIdentitySnapshot
    source_jti: str
    client_ip: str
    throttle_buckets: tuple[str, ...]
    locked_usernames: frozenset[str]
    resources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdentityMutationRequest:
    binding: IdentityMutationBinding
    current_password: str
    deadline_monotonic: float
    requested_username: str | None


@dataclass(frozen=True, slots=True)
class VerifiedIdentityMutationParticipants:
    actor_record: JSONDict
    target_record: JSONDict
    actor: UserIdentitySnapshot
    target: UserIdentitySnapshot
    source_jti: str


async def _admit_identity_mutation(
    *,
    request: Request,
    api_context: ApiContext,
    binding: IdentityMutationBinding,
    requested_username: str | None,
) -> IdentityMutationAdmission | IdentityMutationOutcome:
    await enforce_identity_mutation_attempt_limit(
        request,
        api_context,
        actor_or_source=str(binding.actor_user_id),
    )
    if await has_terminal_identity_mutation(
        api_context.dependencies.database_user_mutations,
        binding,
    ):
        return await build_identity_mutation_replay(
            request=request,
            api_context=api_context,
            binding=binding,
        )
    actor_record = await api_context.dependencies.database_users.get_human_user_by_id(
        binding.actor_user_id
    )
    target_record = await api_context.dependencies.database_users.get_human_user_by_id(
        binding.target_user_id
    )
    if actor_record is None or target_record is None:
        raise ApiError("User not found.", code="not_found", http_status=404)
    initial_actor = user_identity_snapshot_from_record(actor_record)
    initial_target = user_identity_snapshot_from_record(target_record)
    client_ip = resolve_client_host(request, default="")
    throttle_buckets = build_webui_login_failure_buckets(client_ip, initial_actor.username)
    username_values = {initial_actor.username, initial_target.username}
    if requested_username is not None:
        username_values.add(requested_username)
    locked_usernames = frozenset(username_values)
    username_resources = tuple(
        username_auth_resource(username) for username in sorted(locked_usernames)
    )
    source_jti = require_request_session_jti(request)
    return IdentityMutationAdmission(
        binding=binding,
        initial_actor=initial_actor,
        initial_target=initial_target,
        source_jti=source_jti,
        client_ip=client_ip,
        throttle_buckets=throttle_buckets,
        locked_usernames=locked_usernames,
        resources=(
            *throttle_buckets,
            *username_resources,
            session_mutation_resource(source_jti),
        ),
    )


async def _verify_identity_mutation_under_lock(
    *,
    request: Request,
    api_context: ApiContext,
    admission: IdentityMutationAdmission,
    current_password: str,
    deadline_monotonic: float,
) -> VerifiedIdentityMutationParticipants | IdentityMutationOutcome:
    binding = admission.binding
    actor_record = await api_context.dependencies.database_users.get_human_user_by_id(
        binding.actor_user_id
    )
    target_record = await api_context.dependencies.database_users.get_human_user_by_id(
        binding.target_user_id
    )
    if actor_record is None or target_record is None:
        raise ApiError("User not found.", code="not_found", http_status=404)
    actor = user_identity_snapshot_from_record(actor_record)
    target = user_identity_snapshot_from_record(target_record)
    if (
        actor.username not in admission.locked_usernames
        or target.username not in admission.locked_usernames
    ):
        return await fail_identity_mutation_and_replay(
            request=request,
            api_context=api_context,
            binding=binding,
            error_code="user_state_conflict",
        )
    committed_during_proof = await verify_identity_mutation_actor_password(
        request=request,
        api_context=api_context,
        binding=binding,
        actor=actor,
        current_password=current_password,
        deadline_monotonic=deadline_monotonic,
        throttle_buckets=admission.throttle_buckets,
        client_ip=admission.client_ip,
    )
    if committed_during_proof:
        return await build_identity_mutation_replay(
            request=request,
            api_context=api_context,
            binding=binding,
        )
    return VerifiedIdentityMutationParticipants(
        actor_record=actor_record,
        target_record=target_record,
        actor=actor,
        target=target,
        source_jti=admission.source_jti,
    )


@asynccontextmanager
async def verified_identity_mutation(
    request: Request,
    api_context: ApiContext,
    mutation_request: IdentityMutationRequest,
) -> AsyncGenerator[VerifiedIdentityMutationParticipants | IdentityMutationOutcome]:
    admission_result = await _admit_identity_mutation(
        request=request,
        api_context=api_context,
        binding=mutation_request.binding,
        requested_username=mutation_request.requested_username,
    )
    if isinstance(admission_result, IdentityMutationOutcome):
        yield admission_result
        return
    async with lock_webui_auth_resources(
        api_context.dependencies.login_attempt_locks,
        admission_result.resources,
    ):
        yield await _verify_identity_mutation_under_lock(
            request=request,
            api_context=api_context,
            admission=admission_result,
            current_password=mutation_request.current_password,
            deadline_monotonic=mutation_request.deadline_monotonic,
        )


__all__ = (
    "IdentityMutationRequest",
    "VerifiedIdentityMutationParticipants",
    "verified_identity_mutation",
)
