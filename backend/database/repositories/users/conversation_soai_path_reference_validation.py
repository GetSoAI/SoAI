"""SoAI - Conversation SoAI path reference canonicalization [backend/database/repositories/users/conversation_soai_path_reference_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, ValidationError
from core.openai.model_settings_validation import validate_model_settings
from core.workspaces.conversation_workspace_path import (
    fingerprint_conversation_workspace_root,
    read_conversation_workspace_path_override,
    resolve_effective_conversation_workspace_path,
)
from core.workspaces.soai_path_content_validation import validate_soai_path_content_part
from core.workspaces.soai_path_part_fields import (
    source_reference_value,
    target_fingerprint_value,
    tool_reference_value,
)
from core.workspaces.soai_path_resolution import build_soai_path_content_part
from database.core.query_execution import sync_fetch_one_as_dict

if TYPE_CHECKING:
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict

__all__ = ("sync_canonicalize_soai_path_references",)


def _load_workspace_row(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> tuple[str, JSONDict]:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT u.workspace_path, c.model_settings
            FROM webui_conversations c
            JOIN webui_users u ON u.id = c.user_id
            WHERE c.id = ? AND c.user_id = ?
            """,
            (conv_id, user_id),
        ),
    )
    if row is None:
        raise ConflictError("Conversation workspace scope is not available.")
    workspace_path = row.get("workspace_path")
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        raise ConflictError("Conversation workspace scope is invalid.")
    try:
        model_settings = validate_model_settings(row.get("model_settings"))
    except ValidationError as exception:
        raise ConflictError("Conversation model settings are invalid.") from exception
    return workspace_path, model_settings


def _require_workspace_fingerprint(part: JSONDict, expected_fingerprint: str) -> None:
    workspace_scope = part.get("workspace_scope")
    if not isinstance(workspace_scope, dict):
        raise ConflictError("SoAI path workspace scope is invalid.")
    if workspace_scope.get("root_fingerprint") != expected_fingerprint:
        raise ConflictError("SoAI path workspace scope changed before message write.")


def _require_entry_type_match(incoming: JSONDict, canonical: JSONDict) -> None:
    if incoming.get("entry_type") != canonical.get("entry_type"):
        raise ConflictError("SoAI path target type changed before message write.")


def _require_target_identity_match(incoming: JSONDict, canonical: JSONDict) -> None:
    if target_fingerprint_value(incoming) != target_fingerprint_value(canonical):
        raise ConflictError("SoAI path target changed before message write.")
    if tool_reference_value(incoming) != tool_reference_value(canonical):
        raise ConflictError("SoAI path tool reference changed before message write.")


def _canonicalize_part(
    part: JSONDict,
    *,
    effective_root: str,
    root_fingerprint: str,
    resolved_at_ms: int,
) -> JSONDict:
    try:
        validated_part = validate_soai_path_content_part(part)
    except ValidationError as exception:
        raise ConflictError("SoAI path content part is invalid.") from exception
    _require_workspace_fingerprint(validated_part, root_fingerprint)
    try:
        canonical = build_soai_path_content_part(
            effective_workspace_root=effective_root,
            root_fingerprint=root_fingerprint,
            conversation_virtual_path=source_reference_value(validated_part),
            resolved_at_ms=resolved_at_ms,
        )
    except ValidationError as exception:
        raise ConflictError(
            "SoAI path target could not be verified before message write.",
        ) from exception
    _require_entry_type_match(validated_part, canonical)
    _require_target_identity_match(validated_part, canonical)
    return canonical


def _has_soai_path_parts(messages: list[JSONDict]) -> bool:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "soai_path":
                return True
    return False


def _canonicalize_messages(
    messages: list[JSONDict],
    *,
    effective_root: str,
    root_fingerprint: str,
    resolved_at_ms: int,
) -> list[JSONDict]:
    canonical_messages: list[JSONDict] = []
    for message in messages:
        next_message = dict(message)
        content = next_message.get("content")
        if next_message.get("role") != "user" or not isinstance(content, list):
            canonical_messages.append(next_message)
            continue
        canonical_content: list[JSONDict | str] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "soai_path":
                if isinstance(part, str):
                    canonical_content.append(part)
                elif isinstance(part, dict):
                    canonical_content.append(dict(part))
                else:
                    raise ConflictError("Conversation content part is invalid.")
                continue
            canonical_content.append(
                _canonicalize_part(
                    dict(part),
                    effective_root=effective_root,
                    root_fingerprint=root_fingerprint,
                    resolved_at_ms=resolved_at_ms,
                ),
            )
        next_message["content"] = canonical_content
        canonical_messages.append(next_message)
    return canonical_messages


def sync_canonicalize_soai_path_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    messages: list[JSONDict],
    files: FilesProtocol | None,
    resolved_at_ms: int,
) -> list[JSONDict]:
    if not _has_soai_path_parts(messages):
        return [dict(message) for message in messages]
    if files is None:
        raise ConflictError("SoAI path workspace resolver is not available.")
    workspace_path, model_settings = _load_workspace_row(conn, conv_id=conv_id, user_id=user_id)
    effective_root = resolve_effective_conversation_workspace_path(
        files=files,
        user_workspace_path=workspace_path,
        override_workspace_path=read_conversation_workspace_path_override(model_settings),
        require_existing_directories=True,
    )
    fingerprint = fingerprint_conversation_workspace_root(effective_root)
    return _canonicalize_messages(
        messages,
        effective_root=effective_root,
        root_fingerprint=fingerprint,
        resolved_at_ms=resolved_at_ms,
    )
