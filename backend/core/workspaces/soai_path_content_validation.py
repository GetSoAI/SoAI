"""SoAI - WebUI SoAI path content record validation [backend/core/workspaces/soai_path_content_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.content_part_validation_primitives import (
    require_content_part_dict,
    require_content_part_optional_string,
    require_content_part_string,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import require_non_negative_int_strict
from core.workspaces.soai_path_fingerprints import require_soai_path_fingerprint_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("require_canonical_soai_path_source_value", "validate_soai_path_content_part")

_ALLOWED_FIELDS = frozenset(
    (
        "type",
        "entry_type",
        "source_reference",
        "tool_reference",
        "workspace_scope",
        "target_fingerprint",
        "title",
        "preview_type",
        "mime_type",
        "size_bytes",
        "modified_at_ms",
        "resolved_at_ms",
    ),
)
_SOURCE_REFERENCE_FIELDS = frozenset(("type", "value"))
_TOOL_REFERENCE_FIELDS = frozenset(("type", "value"))
_WORKSPACE_SCOPE_FIELDS = frozenset(("type", "root_fingerprint"))
_TARGET_FINGERPRINT_FIELDS = frozenset(("type", "value"))
_MAX_PATH_CHARS = 2048
_MAX_TITLE_CHARS = 512
_MAX_MIME_TYPE_CHARS = 256


def require_canonical_soai_path_source_value(value: JSONValue) -> str:
    virtual_path = require_content_part_string(
        value,
        message="SoAI path source_reference.value must be a non-empty string.",
    )
    if virtual_path != virtual_path.strip():
        raise ValidationError("SoAI path source_reference.value must be canonical.")
    if not virtual_path.startswith("/") or virtual_path == "/":
        raise ValidationError("SoAI path source_reference.value must be canonical.")
    if "\\" in virtual_path or "\x00" in virtual_path:
        raise ValidationError("SoAI path source_reference.value must be canonical.")
    if len(virtual_path) > _MAX_PATH_CHARS:
        raise ValidationError("SoAI path source_reference.value is too long.")
    parts = virtual_path[1:].split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValidationError("SoAI path source_reference.value must be canonical.")
    return virtual_path


def _require_canonical_workspace_relative_path(value: JSONValue) -> str:
    tool_path = require_content_part_string(
        value,
        message="SoAI path tool_reference.value must be a non-empty string.",
    )
    if tool_path != tool_path.strip():
        raise ValidationError("SoAI path tool_reference.value must be canonical.")
    if tool_path.startswith("/") or "\\" in tool_path or "\x00" in tool_path:
        raise ValidationError("SoAI path tool_reference.value must be canonical.")
    if len(tool_path) > _MAX_PATH_CHARS:
        raise ValidationError("SoAI path tool_reference.value is too long.")
    parts = tool_path.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValidationError("SoAI path tool_reference.value must be canonical.")
    return tool_path


def _validate_source_reference(value: JSONValue) -> JSONDict:
    source_reference = require_content_part_dict(
        value,
        message="SoAI path source_reference must be an object.",
    )
    _reject_nested_fields(source_reference, _SOURCE_REFERENCE_FIELDS, "source_reference")
    if source_reference.get("type") != "conversation_virtual_path":
        raise ValidationError(
            "SoAI path source_reference.type must be 'conversation_virtual_path'.",
        )
    return {
        "type": "conversation_virtual_path",
        "value": require_canonical_soai_path_source_value(source_reference.get("value")),
    }


def _validate_tool_reference(value: JSONValue) -> JSONDict:
    tool_reference = require_content_part_dict(
        value,
        message="SoAI path tool_reference must be an object.",
    )
    _reject_nested_fields(tool_reference, _TOOL_REFERENCE_FIELDS, "tool_reference")
    if tool_reference.get("type") != "workspace_relative_path":
        raise ValidationError("SoAI path tool_reference.type must be 'workspace_relative_path'.")
    return {
        "type": "workspace_relative_path",
        "value": _require_canonical_workspace_relative_path(tool_reference.get("value")),
    }


def _validate_workspace_scope(value: JSONValue) -> JSONDict:
    workspace_scope = require_content_part_dict(
        value,
        message="SoAI path workspace_scope must be an object.",
    )
    _reject_nested_fields(workspace_scope, _WORKSPACE_SCOPE_FIELDS, "workspace_scope")
    if workspace_scope.get("type") != "conversation_effective_workspace":
        raise ValidationError(
            "SoAI path workspace_scope.type must be 'conversation_effective_workspace'.",
        )
    root_fingerprint = require_content_part_string(
        workspace_scope.get("root_fingerprint"),
        message="SoAI path workspace_scope.root_fingerprint must be a non-empty string.",
    )
    return {
        "type": "conversation_effective_workspace",
        "root_fingerprint": require_soai_path_fingerprint_value(
            root_fingerprint,
            field="workspace_scope.root_fingerprint",
        ),
    }


def _reject_nested_fields(part: JSONDict, allowed: frozenset[str], label: str) -> None:
    for field_name in part:
        if field_name not in allowed:
            raise ValidationError(f"SoAI path {label} contains unsupported field '{field_name}'.")


def _validate_target_fingerprint(value: JSONValue, *, entry_type: str) -> JSONDict:
    target_fingerprint = require_content_part_dict(
        value,
        message="SoAI path target_fingerprint must be an object.",
    )
    _reject_nested_fields(target_fingerprint, _TARGET_FINGERPRINT_FIELDS, "target_fingerprint")
    fingerprint_type = require_content_part_string(
        target_fingerprint.get("type"),
        message="SoAI path target_fingerprint.type must be a non-empty string.",
    )
    expected_type = "file_sha256" if entry_type == "file" else "folder_listing_sha256"
    if fingerprint_type != expected_type:
        raise ValidationError("SoAI path target_fingerprint.type is invalid.")
    fingerprint_value = require_content_part_string(
        target_fingerprint.get("value"),
        message="SoAI path target_fingerprint.value must be a non-empty string.",
    )
    return {
        "type": expected_type,
        "value": require_soai_path_fingerprint_value(
            fingerprint_value,
            field="target_fingerprint.value",
        ),
    }


def _require_limited_string(value: JSONValue, *, message: str, max_length: int) -> str:
    normalized = require_content_part_string(value, message=message)
    if "\x00" in normalized or len(normalized) > max_length:
        raise ValidationError(message)
    return normalized


def validate_soai_path_content_part(part: JSONDict) -> JSONDict:
    for field_name in part:
        if field_name not in _ALLOWED_FIELDS:
            raise ValidationError(
                f"SoAI path content part contains unsupported field '{field_name}'.",
            )
    if part.get("type") != "soai_path":
        raise ValidationError("SoAI path content part type must be 'soai_path'.")
    entry_type = require_content_part_string(
        part.get("entry_type"),
        message="SoAI path entry_type must be a non-empty string.",
    )
    if entry_type not in ("file", "folder"):
        raise ValidationError("SoAI path entry_type must be 'file' or 'folder'.")
    preview_type = require_content_part_string(
        part.get("preview_type"),
        message="SoAI path preview_type must be a non-empty string.",
    )
    if preview_type not in ("text", "folder", "image", "audio", "video", "document", "file"):
        raise ValidationError("SoAI path preview_type is invalid.")
    source_reference = _validate_source_reference(part.get("source_reference"))
    tool_reference = _validate_tool_reference(part.get("tool_reference"))
    workspace_scope = _validate_workspace_scope(part.get("workspace_scope"))
    target_fingerprint = _validate_target_fingerprint(
        part.get("target_fingerprint"),
        entry_type=entry_type,
    )
    title = _require_limited_string(
        part.get("title"),
        message="SoAI path title is required.",
        max_length=_MAX_TITLE_CHARS,
    )
    mime_type = require_content_part_optional_string(
        part.get("mime_type"),
        message="SoAI path mime_type must be a non-empty string.",
    )
    if mime_type is not None and ("\x00" in mime_type or len(mime_type) > _MAX_MIME_TYPE_CHARS):
        raise ValidationError("SoAI path mime_type must be a non-empty string.")
    validated: JSONDict = {
        "type": "soai_path",
        "entry_type": entry_type,
        "source_reference": source_reference,
        "tool_reference": tool_reference,
        "workspace_scope": workspace_scope,
        "target_fingerprint": target_fingerprint,
        "title": title,
        "preview_type": preview_type,
        "mime_type": mime_type,
    }
    if "size_bytes" not in part:
        raise ValidationError("SoAI path size_bytes is required.")
    size_bytes = part.get("size_bytes")
    if size_bytes is None:
        validated["size_bytes"] = None
    else:
        validated["size_bytes"] = require_non_negative_int_strict(
            size_bytes,
            error_message="SoAI path size_bytes must be a non-negative integer.",
        )
    if entry_type == "file" and validated["size_bytes"] is None:
        raise ValidationError("SoAI path file size_bytes must be a non-negative integer.")
    if "modified_at_ms" not in part:
        raise ValidationError("SoAI path modified_at_ms is required.")
    validated["modified_at_ms"] = require_unix_epoch_ms(
        part.get("modified_at_ms"),
        error_message="SoAI path modified_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    if "resolved_at_ms" not in part:
        raise ValidationError("SoAI path resolved_at_ms is required.")
    validated["resolved_at_ms"] = require_unix_epoch_ms(
        part.get("resolved_at_ms"),
        error_message="SoAI path resolved_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    return validated
