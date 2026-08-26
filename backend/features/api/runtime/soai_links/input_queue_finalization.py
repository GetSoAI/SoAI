"""SoAI - SoAI path finalization for input queue prompts [backend/features/api/runtime/soai_links/input_queue_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part
from core.workspaces.soai_path_part_fields import (
    source_reference_value,
    target_fingerprint_value,
    tool_reference_value,
    workspace_fingerprint,
)
from core.workspaces.soai_path_resolution import build_soai_path_content_part
from features.api.runtime.conversation_workspace_scope import (
    build_conversation_workspace_scope,
)
from features.api.runtime.soai_links.content_parts import (
    message_content_from_text_and_attachments,
    split_finalized_message_content,
)
from features.api.runtime.soai_links.message_finalization import (
    finalize_soai_links_in_messages,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext
    from features.api.runtime.conversation_workspace_scope import (
        ConversationWorkspaceScope,
    )
    from features.api.runtime.user_types import CurrentUser

__all__ = ("finalize_input_queue_soai_links",)


def _contains_soai_path_part(content: JSONValue) -> bool:
    if not isinstance(content, list):
        return False
    for part in content:
        if isinstance(part, dict) and part.get("type") == "soai_path":
            return True
    return False


def _canonicalize_soai_path_parts(
    *,
    content: JSONValue,
    scope: ConversationWorkspaceScope,
) -> JSONValue:
    if not isinstance(content, list):
        return content
    canonical_content: list[JSONValue] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "soai_path":
            canonical_content.append(part)
            continue
        validated = validate_soai_path_content_part(dict(part))
        if workspace_fingerprint(validated) != scope.root_fingerprint:
            raise ValidationError("SoAI path workspace scope is stale.")
        canonical_part = build_soai_path_content_part(
            effective_workspace_root=scope.effective_root_real,
            root_fingerprint=scope.root_fingerprint,
            conversation_virtual_path=source_reference_value(validated),
        )
        if validated.get("entry_type") != canonical_part.get("entry_type"):
            raise ValidationError("SoAI path target type changed before enqueue.")
        if target_fingerprint_value(validated) != target_fingerprint_value(canonical_part):
            raise ValidationError("SoAI path target changed before enqueue.")
        if tool_reference_value(validated) != tool_reference_value(canonical_part):
            raise ValidationError("SoAI path tool reference changed before enqueue.")
        canonical_content.append(canonical_part)
    return canonical_content


async def finalize_input_queue_soai_links(
    *,
    text: str | None,
    attachment_content: list[JSONValue],
    current_user: CurrentUser,
    conversation_record: JSONDict,
    api_context: ApiContext,
) -> tuple[str | None, list[JSONValue]]:
    finalized_messages = await finalize_soai_links_in_messages(
        messages=[
            {
                "role": "user",
                "content": message_content_from_text_and_attachments(text, attachment_content),
            },
        ],
        current_user=current_user,
        conversation_record=conversation_record,
        api_context=api_context,
    )
    if len(finalized_messages) != 1:
        raise ValidationError("Input queue finalization produced an invalid message count.")
    finalized_content = finalized_messages[0].get("content")
    if _contains_soai_path_part(finalized_content):
        scope = build_conversation_workspace_scope(
            current_user=current_user,
            conversation_record=conversation_record,
            api_context=api_context,
        )
        finalized_content = _canonicalize_soai_path_parts(
            content=finalized_content,
            scope=scope,
        )
    return split_finalized_message_content(finalized_content)
