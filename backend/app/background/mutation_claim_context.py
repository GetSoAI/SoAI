"""SoAI - Durable mutation claim execution context [backend/app/background/mutation_claim_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.mutation_requests import MutationClaim
from core.errors.exceptions import StateError
from core.mutations.identifiers import build_mutation_claim_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_system_id
from core.state.access import AccessAction
from core.tasks.task import Task

__all__ = ("build_mutation_claim_request_context",)


def _resolve_access_action(authorization_scope: str) -> AccessAction:
    if authorization_scope == "plugin_admin":
        return AccessAction.PLUGIN_ADMIN
    if authorization_scope == "host_management_admin":
        return AccessAction.HOST_MANAGEMENT_ADMIN
    raise StateError("Accepted mutation authorization scope is unsupported.")


def build_mutation_claim_request_context(
    claim: MutationClaim,
    task: Task,
) -> RequestContext:
    access_action = _resolve_access_action(claim.authorization_scope)
    base_cancellation_id = task.cancellation_id
    if claim.attempt_count > 1:
        base_cancellation_id = create_system_id(
            subsystem="mutation_recovery",
            owner=claim.request_id,
            include_random_suffix=False,
        )
    return RequestContext(
        trace_id=create_system_id(
            subsystem="mutation_recovery",
            owner=claim.request_id,
            include_random_suffix=False,
        ),
        task_id=claim.task_id,
        mutation_fencing_token=claim.fencing_token,
        cancellation_id=build_mutation_claim_cancellation_id(
            base_cancellation_id,
            claim.request_id,
            claim.fencing_token,
        ),
        user_id=task.user_id,
        access_actions=frozenset((access_action,)),
    )
