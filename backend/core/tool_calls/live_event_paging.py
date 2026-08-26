"""SoAI - Tool-call live event paging bounds [backend/core/tool_calls/live_event_paging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "TOOL_CALL_LIVE_EVENT_PAGE_DEFAULT_LIMIT",
    "TOOL_CALL_LIVE_EVENT_PAGE_MAX_LIMIT",
    "resolve_tool_call_live_event_page_limit",
)

TOOL_CALL_LIVE_EVENT_PAGE_DEFAULT_LIMIT = 50
TOOL_CALL_LIVE_EVENT_PAGE_MAX_LIMIT = 200


def resolve_tool_call_live_event_page_limit(limit: int | None) -> int:
    if limit is None:
        return TOOL_CALL_LIVE_EVENT_PAGE_DEFAULT_LIMIT
    if limit < 1:
        raise ValidationError("Tool call live event page limit must be positive.")
    if limit > TOOL_CALL_LIVE_EVENT_PAGE_MAX_LIMIT:
        raise ValidationError(
            f"Tool call live event page limit cannot exceed {TOOL_CALL_LIVE_EVENT_PAGE_MAX_LIMIT}.",
        )
    return limit
