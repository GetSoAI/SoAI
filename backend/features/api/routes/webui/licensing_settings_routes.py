"""SoAI - Authenticated licensing administration routes [backend/features/api/routes/webui/licensing_settings_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import ConcurrencyError
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.webui.licensing_legal_documents import (
    register_licensing_legal_document_route,
    require_current_license_document,
)
from features.api.routes.webui.licensing_offline_import import import_offline_entitlement
from features.api.routes.webui.licensing_rate_admission import (
    enforce_licensing_mutation_rate,
)
from features.api.routes.webui.licensing_status_projection import (
    build_licensing_settings_status,
)
from features.api.routes.webui.licensing_transition_routes import (
    register_licensing_transition_routes,
)
from features.api.routes.webui.request_validators import require_user_id
from features.api.routes.webui.webui_auth_resource_locking import (
    licensing_mutation_resource,
    lock_webui_auth_resources,
)
from features.api.routes.webui.wizard_offline_routes import export_offline_request
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, raise_api_error, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.response_body import create_json_body_response
from features.api.schemas.licensing import (
    LicensingDeactivationRequest,
    LicensingOfflineRequest,
    WizardActivationRequest,
    WizardLicenseAcceptance,
    WizardLicensingMutation,
    WizardUseDeclaration,
)


def _raise_revision_conflict(request: Request) -> None:
    raise_api_error(
        request,
        409,
        "wizard_state_changed",
        "Licensing state changed in another request.",
    )


def register_licensing_settings_routes(routers: ApiRouters) -> None:
    router = routers.webui
    dependencies = require_action_dependencies(AccessAction.LICENSING_ADMIN)
    register_licensing_transition_routes(routers)
    register_licensing_legal_document_route(routers)

    @router.get("/licensing/status", dependencies=dependencies)
    async def licensing_status(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.post("/licensing/license/accept", dependencies=dependencies)
    async def accept_current_license(
        request: Request,
        payload: WizardLicenseAcceptance,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "cheap")
        policy = api_context.dependencies.licensing_policy
        document = await require_current_license_document(request, api_context, payload.fingerprint)
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (licensing_mutation_resource(),),
            ):
                await api_context.dependencies.database_licensing_wizard.accept_current_license(
                    edition=policy.edition,
                    expected_revision=payload.draft_revision,
                    fingerprint=document.fingerprint,
                    accepted_at_ms=epoch_ms(),
                    actor_user_id=require_user_id(request, current_user),
                )
        except ConcurrencyError:
            _raise_revision_conflict(request)
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.post("/licensing/activation", dependencies=dependencies)
    async def activate(
        request: Request,
        payload: WizardActivationRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (licensing_mutation_resource(),),
            ):
                operations = api_context.dependencies.authenticated_licensing_operations
                await operations.activate(payload.to_licensing_input(epoch_ms()))
        except ConcurrencyError:
            _raise_revision_conflict(request)
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.post("/licensing/operation-reconciliation", dependencies=dependencies)
    async def reconcile_operation(
        request: Request,
        payload: WizardLicensingMutation,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (licensing_mutation_resource(),),
            ):
                operations = api_context.dependencies.authenticated_licensing_operations
                await operations.reconcile_operation(
                    draft_revision=payload.draft_revision,
                    now_ms=epoch_ms(),
                )
        except ConcurrencyError:
            _raise_revision_conflict(request)
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.post("/licensing/deactivation", dependencies=dependencies)
    async def deactivate(
        request: Request,
        payload: LicensingDeactivationRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        async with lock_webui_auth_resources(
            api_context.dependencies.login_attempt_locks,
            (licensing_mutation_resource(),),
        ):
            await api_context.dependencies.licensing_maintenance_operations.deactivate(
                payload.reason,
                epoch_ms(),
            )
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.post("/licensing/offline-request", dependencies=dependencies)
    async def export_offline(
        request: Request,
        payload: LicensingOfflineRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        enforce_licensing_mutation_rate(request, "cheap")
        async with lock_webui_auth_resources(
            api_context.dependencies.login_attempt_locks,
            (licensing_mutation_resource(),),
        ):
            return await export_offline_request(
                request,
                payload,
                api_context,
                wizard_mode=False,
            )

    @router.post("/licensing/offline-import", dependencies=dependencies)
    async def import_offline(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "import")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (licensing_mutation_resource(),),
            ):
                await import_offline_entitlement(request, api_context, disposition="active")
        except ConcurrencyError:
            _raise_revision_conflict(request)
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )

    @router.put("/licensing/declaration", dependencies=dependencies)
    async def change_declaration(
        request: Request,
        payload: WizardUseDeclaration,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "cheap")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (licensing_mutation_resource(),),
            ):
                await api_context.dependencies.licensing_administration_operations.change_declaration(
                    expected_revision=payload.draft_revision,
                    declaration=payload.declaration,
                    attestation_confirmed=payload.attestation_confirmed,
                    attestation_revision=payload.attestation_revision,
                    actor_user_id=require_user_id(request, current_user),
                    now_ms=epoch_ms(),
                )
        except ConcurrencyError:
            _raise_revision_conflict(request)
        return create_json_body_response(
            content=await build_licensing_settings_status(api_context), no_store=True
        )


__all__ = ("register_licensing_settings_routes",)
