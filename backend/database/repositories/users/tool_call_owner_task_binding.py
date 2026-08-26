"""SoAI - Tool call owner task binding policy [backend/database/repositories/users/tool_call_owner_task_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.repositories.users.tool_call_validation import validate_optional_string

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("ToolCallOwnerTaskBinding", "resolve_tool_call_owner_task_binding")


@dataclass(frozen=True, slots=True)
class ToolCallOwnerTaskBinding:
    owner_task_id: str | None
    apply_update: bool


def resolve_tool_call_owner_task_binding(
    *,
    requested_owner_task_id: str | None,
    current_owner_task_id: JSONValue | None,
) -> ToolCallOwnerTaskBinding:
    validated_owner_task_id = validate_optional_string(
        requested_owner_task_id,
        "owner_task_id",
    )
    if validated_owner_task_id is not None:
        validated_owner_task_id = validated_owner_task_id.strip()
        if not validated_owner_task_id:
            raise ValidationError("Tool call field 'owner_task_id' must not be empty.")
    current_owner = validate_optional_string(current_owner_task_id, "owner_task_id")
    if (
        validated_owner_task_id is not None
        and current_owner is not None
        and current_owner != validated_owner_task_id
    ):
        raise ValidationError("Tool call owner_task_id cannot be rebound.")
    return ToolCallOwnerTaskBinding(
        owner_task_id=validated_owner_task_id,
        apply_update=validated_owner_task_id is not None and current_owner is None,
    )
