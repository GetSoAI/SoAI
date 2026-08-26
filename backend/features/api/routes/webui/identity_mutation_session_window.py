"""SoAI - Self-mutation source-session horizon validation [backend/features/api/routes/webui/identity_mutation_session_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.auth.jwt_tokens import require_request_session_expiry_ms
from core.users.identity_mutation_records import IdentityMutationBinding
from features.api.routes.webui.user_mutation_responses import (
    record_identity_mutation_failure,
)
from features.api.runtime.context import ApiContext


async def verify_identity_mutation_session_window(
    request: Request,
    api_context: ApiContext,
    binding: IdentityMutationBinding,
    recovery_horizon_at_ms: int,
) -> bool:
    if require_request_session_expiry_ms(request) >= recovery_horizon_at_ms:
        return False
    return await record_identity_mutation_failure(
        api_context.dependencies.database_user_mutations,
        binding,
        "session_rotation_window_unavailable",
    )


__all__ = ("verify_identity_mutation_session_window",)
