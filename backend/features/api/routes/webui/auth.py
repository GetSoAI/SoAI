"""SoAI - WebUI authentication and wizard routes [backend/features/api/routes/webui/auth.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from core.auth.auth_failure_buckets import build_webui_login_failure_buckets
from core.auth.jwt_tokens import invalidate_current_token, require_request_session_jti
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConcurrencyError, ConflictError, ValidationError
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.licensing.legal_documents import load_licensing_document
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from core.types.json import is_json_dict
from core.users.username_rename import user_identity_snapshot_from_record
from core.validation.integers import is_strict_int
from features.api.routes.webui.auth_cookie import apply_session_cookie
from features.api.routes.webui.licensing_rate_admission import (
    enforce_licensing_mutation_rate,
)
from features.api.routes.webui.licensing_settings_routes import (
    register_licensing_settings_routes,
)
from features.api.routes.webui.login_payloads import read_login_payload_or_raise
from features.api.routes.webui.login_throttling import (
    create_login_throttle_admin_alert_noncritical,
    enforce_login_throttle,
    raise_login_rate_limit,
    record_login_failure,
    reset_login_failures,
)
from features.api.routes.webui.session_invalidation import publish_user_session_invalidation
from features.api.routes.webui.users_common import serialize_user_response
from features.api.routes.webui.webui_auth_resource_locking import (
    build_login_auth_resources,
    lock_webui_auth_resources,
    session_mutation_resource,
    setup_ceremony_resource,
    username_auth_resource,
)
from features.api.routes.webui.wizard_licensing_routes import (
    register_wizard_licensing_routes,
)
from features.api.routes.webui.wizard_status import build_wizard_completion_summary
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, raise_api_error, resolve_api_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_server_error,
    raise_unauthorized,
)
from features.api.schemas.licensing import WizardCompletionRequest

__all__ = (
    "AuthRouteRegistrar",
    "register_routes",
)

LOGGER_NAME = "SoAI.features.api.auth"
OPERATION = "api_auth.complete_wizard"


class AuthRouteRegistrar:

    def __init__(self, router: APIRouter) -> None:
        self.router = router

    def register(self) -> None:
        router = self.router

        @router.post(
            "/wizard/complete",
            status_code=status.HTTP_201_CREATED,
            dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
        )
        async def complete_wizard(
            request: Request,
            payload: WizardCompletionRequest | None = None,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> Response:
            if payload is None:
                raise ValidationError(
                    "Initial admin credentials are required.",
                    trace_id=request.state.context.trace_id,
                )
            enforce_licensing_mutation_rate(request, "completion")
            try:
                webui_manager = api_context.dependencies.webui_manager
                policy = api_context.dependencies.licensing_policy
                current_license = await asyncio.to_thread(
                    load_licensing_document,
                    api_context.dependencies.base_dir,
                    policy.controlling_license_relative_path,
                    policy.legal_catalog_relative_paths,
                )
                async with lock_webui_auth_resources(
                    api_context.dependencies.login_attempt_locks,
                    (
                        setup_ceremony_resource(),
                        username_auth_resource(payload.username),
                    ),
                ):
                    hashed_password = (
                        await api_context.dependencies.login_password_service.hash_password(
                            payload.password,
                        )
                    )
                    completed_at_ms = epoch_ms()
                    expected_pending_digest = (
                        await (
                            api_context.dependencies.licensing_service.validate_pending_completion(
                                expected_revision=payload.draft_revision,
                                now_ms=completed_at_ms,
                            )
                        )
                    )
                    user = await webui_manager.complete_licensing_wizard(
                        edition=policy.edition,
                        expected_revision=payload.draft_revision,
                        current_license_fingerprint=current_license.fingerprint,
                        expected_pending_document_digest=expected_pending_digest,
                        username=payload.username,
                        language=payload.language,
                        hashed_password=hashed_password,
                        completed_at_ms=completed_at_ms,
                    )
                    identity = user_identity_snapshot_from_record(user)
                    log_audit_event(request, "WIZARD_COMPLETED", f"user:{payload.username}")
                    completion_summary = await build_wizard_completion_summary(api_context)
                    response = JSONResponse(
                        content={
                            "message": "Initial admin user created successfully.",
                            "user": serialize_user_response(api_context, user),
                            "completion": completion_summary,
                        },
                        status_code=status.HTTP_201_CREATED,
                        headers={"Cache-Control": "no-store"},
                    )
                    await apply_session_cookie(
                        request,
                        response,
                        api_context,
                        identity.user_id,
                        identity.username,
                        identity.password_revision,
                    )
                    return response
            except ConcurrencyError:
                raise_api_error(
                    request,
                    409,
                    "wizard_state_changed",
                    "Wizard state changed in another request.",
                )
            except ConflictError as exception:
                raise_conflict(request, str(exception))
            except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Error during initial admin creation",
                    operation=OPERATION,
                    trace_id=request.state.context.trace_id,
                )
                raise_server_error(
                    request,
                    "An unexpected error occurred during initial admin creation.",
                )

        @router.post("/auth/login")
        async def login(
            request: Request,
            response: Response,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> dict[str, str]:
            payload = await read_login_payload_or_raise(request, api_context)
            webui_manager = api_context.dependencies.webui_manager
            login_guard = webui_manager.webui_login_guard
            client_ip = resolve_client_host(request, default="")
            throttle_buckets = build_webui_login_failure_buckets(client_ip, payload.username)
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                build_login_auth_resources(throttle_buckets, payload.username),
            ):
                await enforce_login_throttle(request, login_guard, throttle_buckets)
                login_record = (
                    await webui_manager.database_users.get_human_login_record_by_username(
                        payload.username,
                    )
                )
                if login_record is None:
                    password_hash_value = (
                        await api_context.dependencies.login_password_service.timing_safe_sentinel_hash()
                    )
                else:
                    password_hash_value = login_record.hashed_password
                password_valid = (
                    await api_context.dependencies.login_password_service.verify_password(
                        payload.password,
                        password_hash_value,
                    )
                )
                if login_record is None or not password_valid:
                    throttled, retry_at = await record_login_failure(
                        login_guard,
                        throttle_buckets,
                    )
                    if throttled:
                        await create_login_throttle_admin_alert_noncritical(
                            api_context.dependencies.database_notifications
                        )
                        raise_login_rate_limit(request, retry_at)
                    raise_unauthorized(
                        request,
                        "Incorrect username or password",
                    )
                username = login_record.username
                await reset_login_failures(login_guard, client_ip, username)
                registration = await apply_session_cookie(
                    request,
                    response,
                    api_context,
                    login_record.user_id,
                    username,
                    password_revision=login_record.password_revision,
                )
                if registration.revoked_jtis:
                    await publish_user_session_invalidation(
                        api_context.dependencies.event_bus,
                        user_id=registration.user_id,
                        username=username,
                        reason="android_session_replaced",
                        session_jtis=registration.revoked_jtis,
                    )
            return {"message": "Login successful"}

        @router.post("/auth/logout")
        async def logout(
            request: Request,
            api_context: ApiContext = Depends(resolve_api_context),
        ) -> dict[str, str]:
            source_jti = require_request_session_jti(request)
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (session_mutation_resource(source_jti),),
            ):
                revocation = await invalidate_current_token(
                    request,
                    api_context.dependencies.webui_manager.database_tokens,
                )
            user_candidate = request.state.user
            if revocation is not None and revocation.revoked_jtis and is_json_dict(user_candidate):
                user = user_candidate
                user_id = user.get("id")
                if is_strict_int(user_id):
                    log_audit_event(
                        request,
                        "LOGOUT",
                        f"user:{revocation.username}",
                        {"session_jtis": list(revocation.revoked_jtis)},
                    )
            return {"message": "Successfully logged out"}


def register_routes(routers: ApiRouters) -> None:
    register_wizard_licensing_routes(routers)
    register_licensing_settings_routes(routers)
    _auth_registrar = AuthRouteRegistrar(routers.webui)
    _auth_registrar.register()
