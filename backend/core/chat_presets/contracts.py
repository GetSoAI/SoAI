"""SoAI - Chat preset V1 JSON contracts [backend/core/chat_presets/contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict

    type ChatPresetSections = JSONDict
    type ChatPresetMutationStatus = Literal[
        "success",
        "not_found",
        "revision_conflict",
        "revision_exhausted",
        "name_conflict",
        "limit_reached",
        "corrupt_record",
    ]

__all__ = (
    "ChatPresetListResult",
    "ChatPresetMutationResult",
    "ChatPresetProjectedRecord",
    "ChatPresetStoredRow",
)


class ChatPresetStoredRow(TypedDict):
    id: str
    user_id: int
    name: str
    name_key: str
    sections_json: str
    revision: int
    created_at_ms: int
    modified_at_ms: int


class ChatPresetProjectedRecord(TypedDict):
    id: str
    name: str
    sections: ChatPresetSections
    revision: int
    created_at_ms: int
    modified_at_ms: int
    omitted_settings_count: int
    applicable: bool


class ChatPresetMutationResult(TypedDict):
    status: ChatPresetMutationStatus
    preset: ChatPresetProjectedRecord | None


class ChatPresetListResult(TypedDict):
    presets: list[ChatPresetProjectedRecord]
    structurally_invalid_count: int
