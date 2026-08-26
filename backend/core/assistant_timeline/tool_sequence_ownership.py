"""SoAI - Assistant timeline tool sequence ownership validation [backend/core/assistant_timeline/tool_sequence_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("register_tool_call_sequence_index_owner",)


def register_tool_call_sequence_index_owner(
    *,
    sequence_owner_by_sequence_index: dict[int, str],
    call_owner_by_call_id: dict[str, int],
    sequence_index: int,
    call_id: str,
    source: str,
) -> None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id:
        raise ValidationError(f"{source} tool sequence ownership requires a call_id.")
    if sequence_index < 0:
        raise ValidationError(
            f"{source} tool sequence ownership requires a non-negative sequence_index.",
        )
    existing_sequence_index = call_owner_by_call_id.get(normalized_call_id)
    if existing_sequence_index is not None and existing_sequence_index != sequence_index:
        message = "".join(
            (
                f"{source} call_id '{normalized_call_id}' is already owned by sequence_index ",
                f"{existing_sequence_index} and cannot be assigned to sequence_index ",
                f"{sequence_index}.",
            ),
        )
        raise ValidationError(
            message,
        )
    existing_call_id = sequence_owner_by_sequence_index.get(sequence_index)
    if existing_call_id is None:
        sequence_owner_by_sequence_index[sequence_index] = normalized_call_id
        call_owner_by_call_id[normalized_call_id] = sequence_index
        return
    if existing_call_id == normalized_call_id:
        call_owner_by_call_id[normalized_call_id] = sequence_index
        return
    message = "".join(
        (
            f"{source} sequence_index {sequence_index} is already owned by call_id ",
            f"'{existing_call_id}' and cannot be assigned to call_id ",
            f"'{normalized_call_id}'.",
        ),
    )
    raise ValidationError(message)
