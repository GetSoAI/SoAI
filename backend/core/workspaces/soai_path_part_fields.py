"""SoAI - Shared SoAI path content field extraction [backend/core/workspaces/soai_path_part_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "source_reference_value",
    "target_fingerprint_value",
    "tool_reference_value",
    "workspace_fingerprint",
)


def source_reference_value(part: JSONDict) -> str:
    source_reference = part.get("source_reference")
    if not isinstance(source_reference, dict):
        raise ValidationError("SoAI path source_reference is invalid.")
    if source_reference.get("type") != "conversation_virtual_path":
        raise ValidationError("SoAI path source_reference.type is invalid.")
    value = source_reference.get("value")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("SoAI path source_reference.value is invalid.")
    return value


def workspace_fingerprint(part: JSONDict) -> str:
    workspace_scope = part.get("workspace_scope")
    if not isinstance(workspace_scope, dict):
        raise ValidationError("SoAI path workspace_scope is invalid.")
    value = workspace_scope.get("root_fingerprint")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("SoAI path workspace_scope.root_fingerprint is invalid.")
    return value


def tool_reference_value(part: JSONDict) -> str:
    tool_reference = part.get("tool_reference")
    if not isinstance(tool_reference, dict):
        raise ValidationError("SoAI path tool_reference is invalid.")
    if tool_reference.get("type") != "workspace_relative_path":
        raise ValidationError("SoAI path tool_reference.type is invalid.")
    value = tool_reference.get("value")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("SoAI path tool_reference.value is invalid.")
    return value


def target_fingerprint_value(part: JSONDict) -> str:
    target_fingerprint = part.get("target_fingerprint")
    if not isinstance(target_fingerprint, dict):
        raise ValidationError("SoAI path target_fingerprint is invalid.")
    value = target_fingerprint.get("value")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("SoAI path target_fingerprint.value is invalid.")
    return value
