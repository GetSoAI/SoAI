"""SoAI - Request source value definitions [backend/core/runtime/request_sources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from core.errors.exceptions import ValidationError

__all__ = (
    "REQUEST_SOURCE_AUTOMATION",
    "REQUEST_SOURCE_MODEL_TEST",
    "REQUEST_SOURCE_OPENAI",
    "REQUEST_SOURCE_SUBAGENT",
    "REQUEST_SOURCE_SYSTEM",
    "REQUEST_SOURCE_WEBUI_WS",
    "normalize_request_source",
)

REQUEST_SOURCE_OPENAI: Final = "openai"
REQUEST_SOURCE_WEBUI_WS: Final = "webui_ws"
REQUEST_SOURCE_MODEL_TEST: Final = "model_test"
REQUEST_SOURCE_AUTOMATION: Final = "automation"
REQUEST_SOURCE_SUBAGENT: Final = "subagent"
REQUEST_SOURCE_SYSTEM: Final = "system"

if TYPE_CHECKING:
    type RequestSource = Literal[
        "openai",
        "webui_ws",
        "model_test",
        "automation",
        "subagent",
        "system",
    ]
else:
    RequestSource = str


def normalize_request_source(value: str) -> RequestSource | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized == REQUEST_SOURCE_OPENAI:
        return REQUEST_SOURCE_OPENAI
    if normalized == REQUEST_SOURCE_WEBUI_WS:
        return REQUEST_SOURCE_WEBUI_WS
    if normalized == REQUEST_SOURCE_MODEL_TEST:
        return REQUEST_SOURCE_MODEL_TEST
    if normalized == REQUEST_SOURCE_AUTOMATION:
        return REQUEST_SOURCE_AUTOMATION
    if normalized == REQUEST_SOURCE_SUBAGENT:
        return REQUEST_SOURCE_SUBAGENT
    if normalized == REQUEST_SOURCE_SYSTEM:
        return REQUEST_SOURCE_SYSTEM
    raise ValidationError(f"Unsupported request_source: {normalized}")
