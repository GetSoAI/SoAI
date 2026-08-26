"""SoAI - Exact licensing governing-document projection [backend/features/api/routes/webui/licensing_legal_documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.licensing.legal_documents import (
    LicensingDocument,
    load_edition_flow_documents,
    load_licensing_document,
)
from core.licensing.policy import EditionLicensingPolicy
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, raise_api_error, resolve_api_context
from features.api.runtime.response_body import create_json_body_response


def build_licensing_legal_documents(
    project_root: str,
    policy: EditionLicensingPolicy,
    flow: str,
) -> JSONDict:
    documents = load_edition_flow_documents(project_root, policy, flow)
    return {
        "schema_version": 1,
        "flow": flow,
        "documents": [
            {
                "document_id": record.document_id,
                "document_name": record.repository_path.rsplit("/", maxsplit=1)[-1],
                "version": record.version,
                "effective_date": record.effective_date,
                "fingerprint": document.fingerprint,
                "license_text": document.content.decode("utf-8"),
            }
            for record, document in documents
        ],
    }


async def require_current_license_document(
    request: Request,
    api_context: ApiContext,
    fingerprint: str,
) -> LicensingDocument:
    policy = api_context.dependencies.licensing_policy
    document = await asyncio.to_thread(
        load_licensing_document,
        api_context.dependencies.base_dir,
        policy.controlling_license_relative_path,
        policy.legal_catalog_relative_paths,
    )
    if fingerprint != document.fingerprint:
        raise_api_error(request, 409, "license_changed", "The license document changed.")
    return document


def register_wizard_licensing_legal_document_route(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/wizard/licensing/governing-documents/{flow}",
        dependencies=require_action_dependencies(AccessAction.WIZARD_BOOTSTRAP),
    )
    async def governing_documents(
        flow: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _legal_document_response(flow, api_context)


def register_licensing_legal_document_route(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/licensing/governing-documents/{flow}",
        dependencies=require_action_dependencies(AccessAction.LICENSING_ADMIN),
    )
    async def governing_documents(
        flow: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        return await _legal_document_response(flow, api_context)


async def _legal_document_response(flow: str, api_context: ApiContext) -> JSONResponse:
    policy = api_context.dependencies.licensing_policy
    return create_json_body_response(
        content=await asyncio.to_thread(
            build_licensing_legal_documents,
            api_context.dependencies.base_dir,
            policy,
            flow,
        ),
        no_store=True,
    )


__all__ = (
    "build_licensing_legal_documents",
    "register_licensing_legal_document_route",
    "register_wizard_licensing_legal_document_route",
    "require_current_license_document",
)
