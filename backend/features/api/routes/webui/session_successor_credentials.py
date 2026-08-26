"""SoAI - Bounded unique successor credential preparation [backend/features/api/routes/webui/session_successor_credentials.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from core.auth.cookie_authentication import resolve_cookie_token_candidates
from core.auth.cookies import create_auth_token_record, resolve_webui_cookie_names
from core.auth.jwt_claims import AccessTokenRecord
from core.auth.webui_sessions import WebuiSessionDescriptor
from core.errors.exceptions import ApiError, ServiceUnavailableError, StateError
from core.runtime.proxy_headers import resolve_request_scheme
from features.api.runtime.context import ApiContext

SUCCESSOR_JTI_ATTEMPTS = 4


@dataclass(frozen=True, slots=True)
class PreparedSessionSuccessor:
    allocator: SessionSuccessorAllocator
    token: AccessTokenRecord
    descriptor: WebuiSessionDescriptor
    csrf_token: str


class SessionSuccessorAllocator:
    def __init__(self, api_context: ApiContext, operation_id: str | None) -> None:
        self._api_context = api_context
        self._operation_id = operation_id
        self._attempts_remaining = SUCCESSOR_JTI_ATTEMPTS

    async def create(
        self,
        *,
        user_id: int,
        username: str,
        password_revision: int,
    ) -> AccessTokenRecord:
        auth_config = self._api_context.dependencies.auth_config
        primary_secret = auth_config.primary_signing_secret
        if primary_secret is None:
            raise StateError("Authentication signing key is unavailable.")
        while self._attempts_remaining > 0:
            self._attempts_remaining -= 1
            token = create_auth_token_record(
                self._api_context.dependencies.config,
                user_id,
                username,
                password_revision=password_revision,
                secret_key=primary_secret,
                algorithm=auth_config.algorithm,
            )
            if not await self._api_context.dependencies.database_tokens.session_jti_exists(
                jti=token.jti
            ):
                return token
        if self._operation_id is None:
            raise ServiceUnavailableError(
                "Unique successor session identity could not be allocated."
            )
        raise ApiError(
            "Identity mutation successor session could not be allocated.",
            code="identity_mutation_session_collision",
            http_status=503,
            details={"operation_id": self._operation_id},
        )


async def prepare_session_successor(
    request: Request,
    api_context: ApiContext,
    operation_id: str,
    user_id: int,
    source_jti: str,
    username: str,
    password_revision: int,
) -> PreparedSessionSuccessor | None:
    allocator = SessionSuccessorAllocator(api_context, operation_id)
    token = await allocator.create(
        user_id=user_id,
        username=username,
        password_revision=password_revision,
    )
    descriptor = await api_context.dependencies.database_tokens.read_active_session_descriptor(
        user_id=user_id,
        jti=source_jti,
    )
    csrf_candidates = resolve_cookie_token_candidates(
        request,
        cookie_name=resolve_webui_cookie_names(resolve_request_scheme(request)).csrf,
    )
    if descriptor is None or len(csrf_candidates) != 1:
        return None
    return PreparedSessionSuccessor(
        allocator=allocator,
        token=token,
        descriptor=descriptor,
        csrf_token=csrf_candidates[0],
    )


__all__ = (
    "PreparedSessionSuccessor",
    "SUCCESSOR_JTI_ATTEMPTS",
    "SessionSuccessorAllocator",
    "prepare_session_successor",
)
