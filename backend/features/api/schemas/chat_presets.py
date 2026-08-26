"""SoAI - Strict chat preset request envelopes [backend/features/api/schemas/chat_presets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, JsonValue, StrictInt, StrictStr

from core.meta.soai_v1 import SoAIV1StrictModel
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

__all__ = (
    "ChatPresetCreateRequest",
    "ChatPresetRenameRequest",
    "ChatPresetReplaceRequest",
)


class ChatPresetCreateRequest(SoAIV1StrictModel):
    name: StrictStr
    sections: dict[str, JsonValue]


class ChatPresetRenameRequest(SoAIV1StrictModel):
    expected_revision: StrictInt = Field(ge=1, le=JAVASCRIPT_SAFE_INTEGER_MAX)
    name: StrictStr


class ChatPresetReplaceRequest(SoAIV1StrictModel):
    expected_revision: StrictInt = Field(ge=1, le=JAVASCRIPT_SAFE_INTEGER_MAX)
    name: StrictStr
    sections: dict[str, JsonValue]
