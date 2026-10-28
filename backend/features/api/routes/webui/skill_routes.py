"""SoAI - Owner-private skill library and conversation selection routes [backend/features/api/routes/webui/skill_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.errors.exceptions import ConflictError, ValidationError
from core.files.export import build_content_disposition_attachment
from core.skills.limits import MAX_SELECTION_REQUEST_BYTES
from core.skills.selection import canonicalize_skill_selection, require_skill_revision
from core.state.access import AccessAction
from core.validation.object_fields import require_exact_json_fields
from features.api.middleware.acl_enforcement import require_actions
from features.api.routes.webui.skill_import import import_skill
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_not_found
from features.api.runtime.request_payloads import read_bounded_json_dict_payload_or_raise

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    routers.webui.get("/skills")(_list_skills)
    routers.webui.post("/skills/import", status_code=201)(_upload_skill)
    routers.webui.get("/skills/imports/{upload_id}")(_skill_import_receipt)
    routers.webui.post(
        "/skills/import-batch",
        status_code=201,
        dependencies=[Depends(require_actions(AccessAction.MCP_USE))],
    )(_upload_skill_batch)
    routers.webui.get(
        "/skills/import-batches/{upload_id}",
        dependencies=[Depends(require_actions(AccessAction.MCP_USE))],
    )(_skill_import_batch_receipt)
    routers.webui.get("/skills/{skill_id}")(_skill_details)
    routers.webui.get("/skills/{skill_id}/resources")(_skill_resource)
    routers.webui.delete("/skills/{skill_id}")(_remove_skill)
    routers.webui.get("/conversations/{conv_id}/skills")(_get_selection)
    routers.webui.put("/conversations/{conv_id}/skills")(_save_selection)


async def _list_skills(
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await api_context.dependencies.database_skills.library(current_user["id"])
    )


async def _upload_skill(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await import_skill(request, api_context, current_user["id"]), status_code=201
    )


async def _skill_import_receipt(
    request: Request,
    upload_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    receipt = await api_context.dependencies.database_skills.import_receipt(
        current_user["id"], upload_id
    )
    if receipt is None:
        raise_not_found(request, "No committed skill import receipt is visible yet.")
    return JSONResponse(content=receipt)


async def _upload_skill_batch(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await import_skill(request, api_context, current_user["id"], collection=True),
        status_code=201,
    )


async def _skill_import_batch_receipt(
    request: Request,
    upload_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    receipt = await api_context.dependencies.database_skills.import_batch_receipt(
        current_user["id"], upload_id
    )
    if receipt is None:
        raise_not_found(
            request,
            "No committed skill collection receipt is visible yet. Retry with the same upload identity.",
        )
    return JSONResponse(content=receipt)


async def _skill_details(
    skill_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await api_context.dependencies.database_skills.details(current_user["id"], skill_id)
    )


async def _skill_resource(
    skill_id: str,
    path: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    member = await api_context.dependencies.database_skills.resource(
        current_user["id"], skill_id, path
    )
    if member.is_directory:
        raise ValidationError("Select a file to download.")
    return Response(
        content=member.content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": build_content_disposition_attachment(member.path.split("/")[-1]),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


async def _remove_skill(
    skill_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await api_context.dependencies.database_skills.remove(current_user["id"], skill_id)
    )


async def _get_selection(
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    return JSONResponse(
        content=await api_context.dependencies.database_skills.selection(
            current_user["id"], conv_id
        )
    )


async def _save_selection(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    payload = await read_bounded_json_dict_payload_or_raise(
        request,
        max_body_bytes=MAX_SELECTION_REQUEST_BYTES,
        invalid_json_message="Invalid skill selection JSON.",
        invalid_object_message="Skill selection must be an object.",
        payload_too_large_message="Skill selection payload is too large.",
        normalization_error_message="Invalid skill selection.",
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    require_exact_json_fields(
        payload, allowed_fields={"expected_revision", "skill_ids"}, label="Skill selection"
    )
    revision = require_skill_revision(payload.get("expected_revision"))
    skill_ids = canonicalize_skill_selection(payload.get("skill_ids"))
    repository = api_context.dependencies.database_skills
    try:
        return JSONResponse(
            content=await repository.replace_selection(
                current_user["id"], conv_id, revision, skill_ids
            )
        )
    except ConflictError:
        current = await repository.selection(current_user["id"], conv_id)
        raise_conflict(
            request,
            "Skill selection changed. Review the current selection before saving.",
            error_type="skill_selection_conflict",
            extra={"current": current},
        )
