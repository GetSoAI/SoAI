"""SoAI - SoAI path operation request validation [backend/features/api/routes/webui/soai_path_operation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.workspaces.soai_path_content_validation import (
    require_canonical_soai_path_source_value,
    validate_soai_path_content_part,
)
from core.workspaces.soai_path_part_fields import (
    source_reference_value,
    workspace_fingerprint,
)
from core.workspaces.soai_path_resolution import build_soai_path_content_part
from features.api.schemas.json_fields import PydanticJSONValue

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.conversation_workspace_scope import (
        ConversationWorkspaceScope,
    )

__all__ = (
    "SoaiPathOperationRequest",
    "canonical_soai_path_part",
    "no_store_headers",
    "source_reference_value",
)


class SoaiPathOperationRequest(SoAIV1StrictModel):
    content_part: dict[str, PydanticJSONValue] | None = None
    source_reference: dict[str, PydanticJSONValue] | None = None
    workspace_scope: dict[str, PydanticJSONValue] | None = None


def no_store_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Content-Disposition": 'inline; filename="soai-path"',
    }


def _root_fingerprint_from_scope(workspace_scope: dict[str, PydanticJSONValue]) -> str:
    if workspace_scope.get("type") != "conversation_effective_workspace":
        raise ValidationError(
            "SoAI path workspace_scope.type must be 'conversation_effective_workspace'.",
        )
    root_fingerprint = workspace_scope.get("root_fingerprint")
    if not isinstance(root_fingerprint, str) or not root_fingerprint.strip():
        raise ValidationError("SoAI path workspace_scope.root_fingerprint is invalid.")
    return root_fingerprint.strip()


def _source_value_from_reference(
    source_reference: dict[str, PydanticJSONValue],
) -> str:
    if source_reference.get("type") != "conversation_virtual_path":
        raise ValidationError(
            "SoAI path source_reference.type must be 'conversation_virtual_path'.",
        )
    value = source_reference.get("value")
    return require_canonical_soai_path_source_value(value)


def _canonical_part_from_content_part(
    scope: ConversationWorkspaceScope,
    content_part: dict[str, PydanticJSONValue],
) -> JSONDict:
    validated = validate_soai_path_content_part(dict(content_part))
    if workspace_fingerprint(validated) != scope.root_fingerprint:
        raise ValidationError("SoAI path workspace scope is stale.")
    return build_soai_path_content_part(
        effective_workspace_root=scope.effective_root_real,
        root_fingerprint=scope.root_fingerprint,
        conversation_virtual_path=source_reference_value(validated),
    )


def _canonical_part_from_reference(
    scope: ConversationWorkspaceScope,
    source_reference: dict[str, PydanticJSONValue],
    workspace_scope: dict[str, PydanticJSONValue],
) -> JSONDict:
    if _root_fingerprint_from_scope(workspace_scope) != scope.root_fingerprint:
        raise ValidationError("SoAI path workspace scope is stale.")
    return build_soai_path_content_part(
        effective_workspace_root=scope.effective_root_real,
        root_fingerprint=scope.root_fingerprint,
        conversation_virtual_path=_source_value_from_reference(source_reference),
    )


def canonical_soai_path_part(
    scope: ConversationWorkspaceScope,
    body: SoaiPathOperationRequest,
) -> JSONDict:
    if body.content_part is not None:
        if body.source_reference is not None or body.workspace_scope is not None:
            raise ValidationError("SoAI path operation request is ambiguous.")
        return _canonical_part_from_content_part(scope, body.content_part)
    if body.source_reference is None or body.workspace_scope is None:
        raise ValidationError(
            "SoAI path operation request requires content_part or source_reference with workspace_scope.",
        )
    return _canonical_part_from_reference(scope, body.source_reference, body.workspace_scope)
