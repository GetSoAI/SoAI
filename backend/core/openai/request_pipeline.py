"""SoAI - OpenAI request pipeline helpers [backend/core/openai/request_pipeline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.system_api.route_paths import (
    OPENAI_CHAT_COMPLETIONS_PATH,
    OPENAI_COMPLETIONS_PATH,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "apply_openai_stored_chat_completion_model_override",
    "is_openai_chat_completions_path",
    "is_openai_text_completions_path",
)


def is_openai_chat_completions_path(path: str) -> bool:
    return path.endswith(OPENAI_CHAT_COMPLETIONS_PATH)


def is_openai_text_completions_path(path: str) -> bool:
    return path.endswith(OPENAI_COMPLETIONS_PATH)


def apply_openai_stored_chat_completion_model_override(
    payload: JSONDict,
    *,
    override_model_id: str,
) -> JSONDict:
    model_value = payload.get("model")
    current = coerce_optional_trimmed_str(model_value if isinstance(model_value, str) else None)
    normalized_override = coerce_optional_trimmed_str(override_model_id)
    if normalized_override is None or current == normalized_override:
        return payload
    return {
        **payload,
        "model": normalized_override,
    }
