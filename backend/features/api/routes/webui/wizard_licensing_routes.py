"""SoAI - Licensing wizard HTTP routes [backend/features/api/routes/webui/wizard_licensing_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import ConcurrencyError, ValidationError
from core.licensing.legal_documents import load_licensing_document
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.webui.licensing_legal_documents import (
    register_wizard_licensing_legal_document_route,
    require_current_license_document,
)
from features.api.routes.webui.licensing_rate_admission import (
    enforce_licensing_mutation_rate,
)
from features.api.routes.webui.webui_auth_resource_locking import (
    licensing_mutation_resource,
    lock_webui_auth_resources,
    setup_ceremony_resource,
)
from features.api.routes.webui.wizard_offline_routes import register_wizard_offline_routes
from features.api.routes.webui.wizard_status import build_wizard_status
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, raise_api_error, resolve_api_context
from features.api.runtime.current_user import get_optional_current_user
from features.api.runtime.response_body import create_json_body_response
from features.api.schemas.licensing import (
    WizardActivationRequest,
    WizardEvaluationRequest,
    WizardLicenseAcceptance,
    WizardLicensingMutation,
    WizardUseDeclaration,
)


def _raise_wizard_conflict(request: Request) -> None:
    raise_api_error(
        request,
        409,
        "wizard_state_changed",
        "Wizard state changed in another request.",
    )


def register_wizard_licensing_routes(routers: ApiRouters) -> None:
    router = routers.webui
    register_wizard_offline_routes(routers)
    register_wizard_licensing_legal_document_route(routers)

    @router.get("/wizard/status")
    async def wizard_status(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return create_json_body_response(
            content=await build_wizard_status(
                api_context,
                include_completed_details=get_optional_current_user(request) is not None,
            ),
            no_store=True,
        )

    @router.post(
        "/wizard/license/accept",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def accept_license(
        request: Request,
        payload: WizardLicenseAcceptance,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "cheap")
        policy = api_context.dependencies.licensing_policy
        document = await require_current_license_document(request, api_context, payload.fingerprint)
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                await api_context.dependencies.database_licensing_wizard.accept_wizard_license(
                    edition=policy.edition,
                    expected_revision=payload.draft_revision,
                    fingerprint=document.fingerprint,
                    accepted_at_ms=epoch_ms(),
                    actor_user_id=None,
                )
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return create_json_body_response(
            content=await build_wizard_status(api_context), no_store=True
        )

    @router.put(
        "/wizard/use",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def set_use(
        request: Request,
        payload: WizardUseDeclaration,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "cheap")
        policy = api_context.dependencies.licensing_policy
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                await api_context.dependencies.database_licensing_wizard.set_wizard_use(
                    edition=policy.edition,
                    expected_revision=payload.draft_revision,
                    declaration=payload.declaration,
                    attestation_confirmed=payload.attestation_confirmed,
                    attestation_revision=payload.attestation_revision,
                    confirmed_at_ms=epoch_ms(),
                    actor_user_id=None,
                )
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return create_json_body_response(
            content=await build_wizard_status(api_context), no_store=True
        )

    @router.get(
        "/wizard/licensing/evaluation-terms",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def evaluation_terms(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        policy = api_context.dependencies.licensing_policy
        if not policy.organizational_evaluation_permitted:
            raise_api_error(request, 404, "not_found", "Evaluation is unavailable.")
        if policy.evaluation_terms_relative_path is None:
            raise ValidationError("Evaluation terms policy is incomplete.")
        document = await asyncio.to_thread(
            load_licensing_document,
            api_context.dependencies.base_dir,
            policy.evaluation_terms_relative_path,
            policy.legal_catalog_relative_paths,
        )
        return create_json_body_response(
            content={
                "schema_version": 1,
                "edition": policy.edition,
                "document_name": policy.evaluation_terms_name,
                "fingerprint": document.fingerprint,
                "license_text": document.content.decode("utf-8"),
            },
            no_store=True,
        )

    @router.get(
        "/wizard/licensing/personal-purchase-terms",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def personal_purchase_terms(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        policy = api_context.dependencies.licensing_policy
        if policy.personal_purchase_terms_relative_path is None:
            raise_api_error(request, 404, "not_found", "Personal purchase terms are unavailable.")
        document = await asyncio.to_thread(
            load_licensing_document,
            api_context.dependencies.base_dir,
            policy.personal_purchase_terms_relative_path,
            policy.legal_catalog_relative_paths,
        )
        return create_json_body_response(
            content={
                "schema_version": 1,
                "edition": policy.edition,
                "document_name": policy.personal_purchase_terms_name,
                "fingerprint": document.fingerprint,
                "license_text": document.content.decode("utf-8"),
            },
            no_store=True,
        )

    @router.post(
        "/wizard/licensing/evaluation",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def start_evaluation(
        request: Request,
        payload: WizardEvaluationRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        policy = api_context.dependencies.licensing_policy
        if not policy.organizational_evaluation_permitted:
            raise_api_error(request, 404, "not_found", "Evaluation is unavailable.")
        if policy.evaluation_terms_relative_path is None:
            raise ValidationError("Evaluation terms policy is incomplete.")
        document = await asyncio.to_thread(
            load_licensing_document,
            api_context.dependencies.base_dir,
            policy.evaluation_terms_relative_path,
            policy.legal_catalog_relative_paths,
        )
        terms_acceptance = next(
            (
                value
                for value in payload.legal_acceptances
                if value.document_id == "organization_evaluation_terms"
            ),
            None,
        )
        if terms_acceptance is None or document.fingerprint != terms_acceptance.fingerprint:
            raise_api_error(request, 409, "evaluation_terms_changed", "Evaluation terms changed.")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                operations = api_context.dependencies.wizard_licensing_operations
                await operations.evaluate(
                    draft_revision=payload.draft_revision,
                    organization=payload.organization.model_dump(mode="json"),
                    legal_acceptances=[
                        value.model_dump(mode="json") for value in payload.legal_acceptances
                    ],
                    terms_fingerprint=terms_acceptance.fingerprint,
                    now_ms=epoch_ms(),
                )
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return create_json_body_response(
            content=await build_wizard_status(api_context), no_store=True
        )

    @router.post(
        "/wizard/licensing/activation",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def activate(
        request: Request,
        payload: WizardActivationRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                operations = api_context.dependencies.wizard_licensing_operations
                await operations.activate(payload.to_licensing_input(epoch_ms()))
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return create_json_body_response(
            content=await build_wizard_status(api_context), no_store=True
        )

    @router.post(
        "/wizard/licensing/operation-reconciliation",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def reconcile_operation(
        request: Request,
        payload: WizardLicensingMutation,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "online")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                operations = api_context.dependencies.wizard_licensing_operations
                await operations.reconcile_operation(
                    draft_revision=payload.draft_revision,
                    now_ms=epoch_ms(),
                )
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return create_json_body_response(
            content=await build_wizard_status(api_context), no_store=True
        )


__all__ = ("register_wizard_licensing_routes",)
