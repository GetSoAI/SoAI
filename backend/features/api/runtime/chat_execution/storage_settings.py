"""SoAI - Stored chat completion settings resolution [backend/features/api/runtime/chat_execution/storage_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.openai.request_options import extract_openai_store_flag
from core.openai.request_pipeline import is_openai_chat_completions_path
from core.system_api.request_paths import get_scope_path
from features.api.runtime.openai_request_state import (
    read_stored_chat_completion_request_json,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_chat_completion_storage_settings",)


def resolve_chat_completion_storage_settings(
    *,
    request: Request,
    request_json: JSONDict,
) -> tuple[bool, JSONDict]:
    path = get_scope_path(request.scope)
    store_requested = bool(
        is_openai_chat_completions_path(path)
        and extract_openai_store_flag(request_json, default=False),
    )
    stored_request_json = read_stored_chat_completion_request_json(request) or dict(request_json)
    return (bool(store_requested), stored_request_json)
