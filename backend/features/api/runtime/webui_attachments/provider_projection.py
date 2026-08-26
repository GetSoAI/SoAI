"""SoAI - Provider projection for WebUI attachment content parts [backend/features/api/runtime/webui_attachments/provider_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.storage_root_resolution import resolve_managed_files_storage_root
from core.types.json_value import copy_json_dict_list
from core.workspaces.soai_path_link_codec import SOAI_PATH_TOKEN_PREFIX
from features.api.runtime.webui_attachments.file_projection import (
    project_soai_file_for_provider,
)
from features.api.runtime.webui_attachments.knowledge_projection import (
    project_soai_knowledge_for_provider,
)
from features.api.runtime.webui_attachments.projection_context import (
    WebuiAttachmentProjectionContext,
)
from features.api.runtime.webui_attachments.provider_projection_session import (
    ProviderAttachmentProjectionSession,
)
from features.api.runtime.webui_attachments.provider_text_projection_budget import (
    resolve_provider_text_char_budget_for_projection,
)
from features.api.runtime.webui_attachments.provider_video_budget import (
    build_provider_video_allocations,
)
from features.api.runtime.webui_attachments.soai_path_projection import (
    project_soai_path_for_provider,
)
from features.api.runtime.webui_attachments.soai_path_tool_access import (
    resolve_soai_path_tool_access,
)
from features.api.runtime.webui_attachments.unavailable_projection import (
    project_unavailable_attachment_for_provider,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "build_webui_attachment_provider_projector",
    "project_webui_attachments_for_provider",
)


def build_webui_attachment_provider_projector(
    *,
    dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
    model_id: str | None,
) -> Callable[[list[JSONDict]], Awaitable[list[JSONDict]]]:
    session = ProviderAttachmentProjectionSession(
        dependencies=dependencies,
        model_id=model_id,
    )

    async def project_provider_messages(messages: list[JSONDict]) -> list[JSONDict]:
        return await _project_webui_attachments_with_session(
            dependencies=dependencies,
            conv_id=conv_id,
            user_id=user_id,
            model_id=model_id,
            messages=messages,
            session=session,
        )

    return project_provider_messages


def _string(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"WebUI attachment projection field '{field}' must be a string.")
    return value


def _append_projected_part(projected_parts: list[JSONDict], part: JSONDict) -> None:
    if part.get("type") != "text":
        projected_parts.append(part)
        return
    text_value = _string(part.get("text"), field="text").strip()
    if not text_value:
        return
    last_part = projected_parts[-1] if projected_parts else None
    if isinstance(last_part, dict) and last_part.get("type") == "text":
        last_text = _string(last_part.get("text"), field="text").strip()
        last_part["text"] = f"{last_text}\n\n{text_value}" if last_text else text_value
        return
    projected_parts.append({"type": "text", "text": text_value})


def _append_projected_parts(projected_parts: list[JSONDict], parts: list[JSONDict]) -> None:
    for part in parts:
        _append_projected_part(projected_parts, part)


async def _project_content_parts(
    context: WebuiAttachmentProjectionContext,
    parts: list[JSONValue],
) -> list[JSONDict]:
    projected_parts: list[JSONDict] = []
    for part_value in parts:
        if not isinstance(part_value, dict):
            raise ValidationError("Message content part must be an object before projection.")
        part = dict(part_value)
        part_type = part.get("type")
        if part_type == "text":
            text = _string(part.get("text"), field="text")
            if SOAI_PATH_TOKEN_PREFIX in text:
                raise ValidationError(
                    "Provider-bound WebUI message contains an unresolved SoAI path token.",
                )
            if text.strip():
                _append_projected_part(projected_parts, {"type": "text", "text": text})
            continue
        if part_type == "soai_path":
            _append_projected_parts(
                projected_parts,
                await project_soai_path_for_provider(context, part=part),
            )
            continue
        if part_type == "soai_file":
            _append_projected_parts(
                projected_parts,
                await project_soai_file_for_provider(
                    context,
                    part=part,
                ),
            )
            continue
        if part_type == "soai_knowledge":
            _append_projected_parts(
                projected_parts,
                await project_soai_knowledge_for_provider(context, part=part),
            )
            continue
        unavailable_projection = project_unavailable_attachment_for_provider(part)
        if unavailable_projection is not None:
            _append_projected_part(projected_parts, unavailable_projection)
            continue
        if isinstance(part_type, str) and part_type.startswith("soai_"):
            raise ValidationError("Provider-bound WebUI message contains WebUI attachment content.")
        projected_parts.append(part)
    return projected_parts


async def _project_message(
    context: WebuiAttachmentProjectionContext,
    message: JSONDict,
) -> JSONDict:
    projected = dict(message)
    content = projected.get("content")
    if isinstance(content, str):
        if SOAI_PATH_TOKEN_PREFIX in content:
            raise ValidationError(
                "Provider-bound WebUI message contains an unresolved SoAI path token.",
            )
        return projected
    if isinstance(content, list):
        projected["content"] = await _project_content_parts(
            context,
            list(content),
        )
    return projected


def _assert_no_residual_webui_attachments(messages: list[JSONDict]) -> None:
    blocked_types = frozenset(("soai_path", "soai_file", "soai_knowledge"))
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and SOAI_PATH_TOKEN_PREFIX in content:
            raise ValidationError(
                "Provider-bound WebUI message contains an unresolved SoAI path token.",
            )
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            residual_type = part.get("type")
            if residual_type in blocked_types or (
                isinstance(residual_type, str) and residual_type.startswith("soai_")
            ):
                raise ValidationError(
                    "Provider-bound WebUI message contains WebUI attachment content.",
                )
            text_value = part.get("text")
            if isinstance(text_value, str) and SOAI_PATH_TOKEN_PREFIX in text_value:
                raise ValidationError(
                    "Provider-bound WebUI message contains an unresolved SoAI path token.",
                )


async def project_webui_attachments_for_provider(
    *,
    dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
    model_id: str | None,
    messages: list[JSONDict],
) -> list[JSONDict]:
    return await _project_webui_attachments_with_session(
        dependencies=dependencies,
        conv_id=conv_id,
        user_id=user_id,
        model_id=model_id,
        messages=messages,
        session=ProviderAttachmentProjectionSession(
            dependencies=dependencies,
            model_id=model_id,
        ),
    )


async def _project_webui_attachments_with_session(
    *,
    dependencies: ApiDependencies,
    conv_id: str,
    user_id: int,
    model_id: str | None,
    messages: list[JSONDict],
    session: ProviderAttachmentProjectionSession,
) -> list[JSONDict]:
    vision_supported = await session.vision_supported()
    soai_path_tool_access = await resolve_soai_path_tool_access(
        dependencies=dependencies,
        conv_id=conv_id,
        user_id=user_id,
        model_id=model_id,
        messages=messages,
    )
    provider_text_char_budget = await resolve_provider_text_char_budget_for_projection(
        dependencies=dependencies,
        model_id=model_id,
        messages=messages,
        vision_supported=vision_supported,
        soai_path_tool_access=soai_path_tool_access,
    )
    context = WebuiAttachmentProjectionContext(
        dependencies=dependencies,
        conv_id=conv_id,
        user_id=user_id,
        vision_supported=vision_supported,
        soai_path_tool_access=soai_path_tool_access,
        storage_root=resolve_managed_files_storage_root(dependencies.config, dependencies.files),
        provider_text_char_budget=provider_text_char_budget,
        video_session=session,
        video_allocations=(
            build_provider_video_allocations(messages, session.video_settings)
            if vision_supported
            else {}
        ),
    )
    projected = [await _project_message(context, message) for message in messages]
    _assert_no_residual_webui_attachments(projected)
    return copy_json_dict_list(projected)
