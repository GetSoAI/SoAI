"""SoAI - Event publishing helpers for conversation routes [backend/features/api/routes/webui/conversation_event_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Request

from core.events.conversation_publication import publish_conversation_updated
from features.api.runtime.context import ApiContext
from features.api.runtime.validation import (
    require_field,
    require_unix_timestamp_ms,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("publish_conversation_update",)


async def publish_conversation_update(
    request: Request,
    api_context: ApiContext,
    user_id: int,
    conv_id: str,
    record: Mapping[str, JSONValue],
    *,
    title: str | None = None,
    is_favorite: bool | None = None,
    color: str | None = None,
    color_present: bool = False,
    model_settings: JSONDict | None = None,
    is_archived: bool | None = None,
) -> None:
    last_modified_at_ms = require_unix_timestamp_ms(
        request,
        require_field(request, record, "last_modified_at_ms"),
        field="last_modified_at_ms",
    )
    await publish_conversation_updated(
        api_context.dependencies.event_bus,
        user_id=user_id,
        conv_id=conv_id,
        last_modified_at_ms=last_modified_at_ms,
        title=title,
        is_favorite=is_favorite,
        color=color,
        color_present=color_present,
        model_settings=model_settings,
        is_archived=is_archived,
    )
