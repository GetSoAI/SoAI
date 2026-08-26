"""SoAI - Wizard offline licensing routes [backend/features/api/routes/webui/wizard_offline_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from uuid import uuid4

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import ConcurrencyError, StateError
from core.licensing.constants import (
    LICENSING_DRAFT_REVISION_HEADER,
    LICENSING_REQUEST_DIGEST_HEADER,
    OFFLINE_REQUEST_FILENAME,
    OFFLINE_REQUEST_MEDIA_TYPE,
)
from core.licensing.license_acceptance import require_current_license_acceptance
from core.licensing.machine_protocol import prepare_offline_activation_request
from core.licensing.storage_records import OfflineRequestInsert
from core.meta.instance_identity import resolve_instance_identity
from core.meta.version import __version__
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.webui.licensing_offline_import import import_offline_entitlement
from features.api.routes.webui.licensing_rate_admission import (
    enforce_licensing_mutation_rate,
)
from features.api.routes.webui.webui_auth_resource_locking import (
    licensing_mutation_resource,
    lock_webui_auth_resources,
    setup_ceremony_resource,
)
from features.api.routes.webui.wizard_status import build_wizard_status
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, raise_api_error, resolve_api_context
from features.api.schemas.licensing import LicensingOfflineRequest


def _raise_wizard_conflict(request: Request) -> None:
    raise_api_error(
        request,
        409,
        "wizard_state_changed",
        "Wizard state changed in another request.",
    )


def register_wizard_offline_routes(routers: ApiRouters) -> None:
    router = routers.webui

    @router.post(
        "/wizard/licensing/offline-request",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def export_wizard_offline_request(
        request: Request,
        payload: LicensingOfflineRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        enforce_licensing_mutation_rate(request, "cheap")
        dependencies = api_context.dependencies
        async with lock_webui_auth_resources(
            dependencies.login_attempt_locks,
            (setup_ceremony_resource(), licensing_mutation_resource()),
        ):
            return await export_offline_request(
                request,
                payload,
                api_context,
                wizard_mode=True,
            )

    @router.post(
        "/wizard/licensing/offline-import",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def import_offline_certificate(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        enforce_licensing_mutation_rate(request, "import")
        try:
            async with lock_webui_auth_resources(
                api_context.dependencies.login_attempt_locks,
                (setup_ceremony_resource(), licensing_mutation_resource()),
            ):
                await import_offline_entitlement(request, api_context, disposition="pending")
        except ConcurrencyError:
            _raise_wizard_conflict(request)
        return JSONResponse(
            content=await build_wizard_status(api_context),
            headers={"Cache-Control": "no-store"},
        )


async def export_offline_request(
    request: Request,
    payload: LicensingOfflineRequest,
    api_context: ApiContext,
    *,
    wizard_mode: bool,
) -> Response:
    dependencies = api_context.dependencies
    policy = dependencies.licensing_policy
    draft = await dependencies.database_licensing_wizard.read_wizard_draft(policy.edition)
    if draft["revision"] != payload.draft_revision:
        _raise_wizard_conflict(request)
    require_current_license_acceptance(
        draft,
        dependencies.licensing_service.controlling_license_fingerprint,
    )
    if draft["declaration"] is None:
        raise_api_error(
            request,
            409,
            "wizard_prerequisite_missing",
            "License acceptance and use declaration are required.",
        )
    if not policy.product_access_required(draft["declaration"]):
        raise_api_error(
            request,
            409,
            "product_access_not_required",
            "Core Personal does not require product activation.",
        )
    now_ms = epoch_ms()
    if wizard_mode:
        draft = await dependencies.database_licensing_wizard.begin_wizard_access(
            edition=policy.edition,
            expected_revision=payload.draft_revision,
            access_flow="offline_activation",
            changed_at_ms=now_ms,
        )
    draft_revision = draft.get("revision")
    if isinstance(draft_revision, bool) or not isinstance(draft_revision, int):
        raise StateError("Licensing wizard draft revision is invalid.")
    identity = await dependencies.database_licensing.deployment_identity(now_ms)
    instance = await resolve_instance_identity(
        dependencies.database_plugins,
        dependencies.database_licensing,
    )
    prepared = prepare_offline_activation_request(
        identity.private_key,
        idempotency_key=secrets.token_urlsafe(24),
        instance_id=instance.instance_id,
        soai_version=str(__version__),
        licensed_product_scope=policy.licensed_product_scope,
        deployment_product=("soai_core" if policy.edition == "soai-core" else "soai_os"),
        deployment_environment=payload.deployment_environment,
        license_reference=payload.license_reference,
    )
    persisted = await dependencies.database_licensing.get_or_create_offline_request(
        OfflineRequestInsert(
            operation_id=str(uuid4()),
            draft_revision=draft_revision,
            edition=policy.edition,
            licensed_product_scope=policy.licensed_product_scope,
            instance_id=instance.instance_id,
            deployment_public_key=identity.public_key,
            request_digest=prepared.request_digest,
            canonical_content=prepared.canonical_document,
            created_at_ms=now_ms,
        )
    )
    return Response(
        content=persisted.canonical_content,
        media_type=OFFLINE_REQUEST_MEDIA_TYPE,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{OFFLINE_REQUEST_FILENAME}"',
            LICENSING_DRAFT_REVISION_HEADER: str(persisted.draft_revision),
            LICENSING_REQUEST_DIGEST_HEADER: persisted.request_digest,
        },
    )


__all__ = ("export_offline_request", "register_wizard_offline_routes")
