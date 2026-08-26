"""SoAI - Authenticated licensing transition routes [backend/features/api/routes/webui/licensing_transition_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.api.routes.webui.licensing_rate_admission import enforce_licensing_mutation_rate
from features.api.routes.webui.licensing_status_projection import build_licensing_settings_status
from features.api.routes.webui.webui_auth_resource_locking import (
    licensing_mutation_resource,
    lock_webui_auth_resources,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response
from features.api.schemas.licensing import (
    LicensingCommercialConversion,
    LicensingDeploymentReclassification,
    LicensingOsEvaluationConversion,
    LicensingOsEvaluationReversion,
    WizardLicensingMutation,
)


def register_licensing_transition_routes(routers: ApiRouters) -> None:
    router = routers.webui
    dependencies = require_action_dependencies(AccessAction.LICENSING_ADMIN)

    @router.post("/licensing/os-evaluation-conversion", dependencies=dependencies)
    async def convert_os_evaluation(
        request: Request,
        payload: LicensingOsEvaluationConversion,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _execute(
            request,
            api_context,
            lambda: api_context.dependencies.licensing_deployment_operations.convert_os_evaluation(
                payload.draft_revision,
                payload.organization.model_dump(mode="json"),
                [value.model_dump(mode="json") for value in payload.legal_acceptances],
                epoch_ms(),
            ),
        )

    @router.post("/licensing/os-evaluation-reversion", dependencies=dependencies)
    async def revert_os_evaluation(
        request: Request,
        payload: LicensingOsEvaluationReversion,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _execute(
            request,
            api_context,
            lambda: api_context.dependencies.licensing_deployment_operations.revert_os_evaluation(
                payload.draft_revision, epoch_ms()
            ),
        )

    @router.post("/licensing/commercial-conversion", dependencies=dependencies)
    async def convert_commercial(
        request: Request,
        payload: LicensingCommercialConversion,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _execute(
            request,
            api_context,
            lambda: api_context.dependencies.licensing_deployment_operations.convert_commercial(
                payload.draft_revision,
                payload.activation_credential,
                payload.deployment_environment,
                [value.model_dump(mode="json") for value in payload.legal_acceptances],
                epoch_ms(),
            ),
        )

    @router.post("/licensing/deployment-reclassification", dependencies=dependencies)
    async def reclassify_deployment(
        request: Request,
        payload: LicensingDeploymentReclassification,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _execute(
            request,
            api_context,
            lambda: api_context.dependencies.licensing_deployment_operations.reclassify(
                payload.draft_revision, payload.deployment_environment, epoch_ms()
            ),
        )

    @router.post("/licensing/term-renewal", dependencies=dependencies)
    async def retrieve_term(
        request: Request,
        payload: WizardLicensingMutation,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _execute(
            request,
            api_context,
            lambda: api_context.dependencies.licensing_deployment_operations.retrieve_term(
                payload.draft_revision, epoch_ms()
            ),
        )


async def _execute(
    request: Request,
    api_context: ApiContext,
    operation: Callable[[], Awaitable[JSONDict]],
) -> JSONResponse:
    enforce_licensing_mutation_rate(request, "online")
    async with lock_webui_auth_resources(
        api_context.dependencies.login_attempt_locks,
        (licensing_mutation_resource(),),
    ):
        await operation()
    return create_json_body_response(
        content=await build_licensing_settings_status(api_context), no_store=True
    )


__all__ = ("register_licensing_transition_routes",)
