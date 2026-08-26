"""SoAI - WebUI session rotation recovery endpoint [backend/features/api/routes/webui/auth_session_rotation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.auth.cookie_authentication import resolve_cookie_token_candidates
from core.auth.cookies import (
    determine_secure_cookie,
    resolve_webui_cookie_names,
    set_auth_cookie_record,
)
from core.auth.jwt_claims import (
    AccessTokenRecord,
    create_exact_access_token_record,
    decode_signed_webui_token,
)
from core.errors.exceptions import SecurityError, StateError
from core.runtime.proxy_headers import resolve_request_scheme
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, is_json_dict
from core.users.user_id import require_strict_user_id
from features.api.routes.webui.identity_mutation_throttling import (
    enforce_identity_mutation_attempt_limit,
)
from features.api.routes.webui.user_mutation_responses import (
    serialize_identity_mutation_record,
    serialize_missing_identity_mutation,
)
from features.api.routes.webui.users_common import serialize_user_response
from features.api.routes.webui.webui_auth_resource_locking import (
    lock_webui_auth_resources,
    session_mutation_resource,
)
from features.api.runtime.auth_request_state import require_request_auth_method
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.users import SessionRotationRecoveryPayload


@dataclass(frozen=True, slots=True)
class RecoveredRequestSession:
    user: JSONDict
    token_record: AccessTokenRecord
    csrf_token: str
    operation_id: str


async def _operation_status(
    api_context: ApiContext,
    actor_user_id: int,
    operation_id: str | None,
) -> JSONDict | None:
    if operation_id is None:
        return None
    record = await api_context.dependencies.database_user_mutations.read_by_actor_operation(
        actor_user_id,
        operation_id,
    )
    if record is None or record.binding.target_user_id != actor_user_id:
        return serialize_missing_identity_mutation(operation_id)
    return serialize_identity_mutation_record(record)


def _request_user(request: Request) -> JSONDict:
    try:
        value = request.state.user
    except AttributeError as exception:
        raise SecurityError("Session rotation authentication is unavailable.") from exception
    if not is_json_dict(value):
        raise SecurityError("Session rotation authentication is unavailable.")
    return value


async def recover_request_session_rotation(
    request: Request,
    api_context: ApiContext,
    expected_operation_id: str | None = None,
) -> RecoveredRequestSession | None:
    auth_config = api_context.dependencies.auth_config
    cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
    token_candidates = resolve_cookie_token_candidates(request, cookie_name=cookie_names.auth)
    csrf_candidates = resolve_cookie_token_candidates(
        request,
        cookie_name=cookie_names.csrf,
    )
    if len(token_candidates) != 1 or len(csrf_candidates) != 1:
        return None
    claims = decode_signed_webui_token(
        token_candidates[0],
        secret_keys=auth_config.verification_secrets,
        algorithm=auth_config.algorithm,
    )
    await enforce_identity_mutation_attempt_limit(
        request,
        api_context,
        actor_or_source=claims.jti,
    )
    async with lock_webui_auth_resources(
        api_context.dependencies.login_attempt_locks,
        (session_mutation_resource(claims.jti),),
    ):
        recovery = (
            await api_context.dependencies.webui_manager.database_tokens.recover_session_rotation(
                source_jti=claims.jti,
                user_id=claims.user_id,
                source_password_revision=claims.password_revision,
                source_issued_at_ms=claims.issued_at_ms,
                source_expires_at_ms=claims.expires_at_ms,
                observed_at_ms=epoch_ms(),
            )
        )
    if recovery.status == "terminal" or recovery.user is None:
        return None
    replacement_jti = recovery.replacement_jti
    replacement_issued_at_ms = recovery.replacement_issued_at_ms
    replacement_expires_at_ms = recovery.replacement_expires_at_ms
    replacement_password_revision = recovery.replacement_password_revision
    if (
        replacement_jti is None
        or replacement_issued_at_ms is None
        or replacement_expires_at_ms is None
        or replacement_password_revision is None
    ):
        raise StateError("Recovered session metadata is incomplete.")
    username = recovery.user.get("username")
    if not isinstance(username, str):
        raise StateError("Recovered session username is invalid.")
    primary_secret = auth_config.primary_signing_secret
    if primary_secret is None:
        raise StateError("Authentication signing key is unavailable.")
    token_record = create_exact_access_token_record(
        primary_secret,
        {
            "uid": claims.user_id,
            "sub": username,
            "pwd_rev": replacement_password_revision,
        },
        jti=replacement_jti,
        issued_at_ms=replacement_issued_at_ms,
        expires_at_ms=replacement_expires_at_ms,
        algorithm=auth_config.algorithm,
    )
    operation_id = recovery.operation_id
    if operation_id is None:
        raise StateError("Recovered session operation identity is incomplete.")
    if expected_operation_id is not None and operation_id != expected_operation_id:
        raise SecurityError("Recovered session is bound to another operation.")
    return RecoveredRequestSession(
        user=recovery.user,
        token_record=token_record,
        csrf_token=csrf_candidates[0],
        operation_id=operation_id,
    )


async def _recover_response(
    request: Request,
    api_context: ApiContext,
    payload: SessionRotationRecoveryPayload,
) -> Response:
    recovered = await recover_request_session_rotation(request, api_context)
    if recovered is None:
        return JSONResponse(content={"status": "terminal"}, headers={"Cache-Control": "no-store"})
    actor_user_id = require_strict_user_id(recovered.user.get("id"))
    operation = await _operation_status(api_context, actor_user_id, payload.operation_id)
    response = JSONResponse(
        content={
            "status": "recovered",
            "user": serialize_user_response(api_context, recovered.user),
            "operation": operation,
        },
    )
    primary_secret = api_context.dependencies.auth_config.primary_signing_secret
    if primary_secret is None:
        raise StateError("Authentication signing key is unavailable.")
    set_auth_cookie_record(
        response,
        api_context.dependencies.config,
        recovered.token_record,
        cookie_names=resolve_webui_cookie_names(resolve_request_scheme(request)),
        secret_key=primary_secret,
        secure_cookie=determine_secure_cookie(
            api_context.dependencies.config,
            request_scheme=resolve_request_scheme(request),
        ),
        csrf_token=recovered.csrf_token,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/auth/session-rotation/recover")
    async def recover_session_rotation(
        request: Request,
        payload: SessionRotationRecoveryPayload,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        auth_method = require_request_auth_method(request)
        user = _request_user(request)
        actor_user_id = require_strict_user_id(user.get("id"))
        if auth_method == "jwt_cookie":
            await enforce_identity_mutation_attempt_limit(
                request,
                api_context,
                actor_or_source=str(actor_user_id),
            )
            operation = await _operation_status(api_context, actor_user_id, payload.operation_id)
            response = JSONResponse(
                content={
                    "status": "active",
                    "user": serialize_user_response(api_context, user),
                    "operation": operation,
                },
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        if auth_method != "jwt_cookie_rotation_recovery":
            raise SecurityError("Session rotation authentication is unavailable.")
        return await _recover_response(request, api_context, payload)


__all__ = ("RecoveredRequestSession", "recover_request_session_rotation", "register_routes")
