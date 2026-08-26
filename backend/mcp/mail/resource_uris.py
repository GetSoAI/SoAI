"""SoAI - Mail MCP resource URI builders [backend/mcp/mail/resource_uris.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.shared.resource_uris import build_resource_uri

__all__ = (
    "MAIL_RESOURCE_URI",
    "build_mail_folder_head_resource_uri",
    "build_mail_message_resource_uri",
)

MAIL_RESOURCE_URI = "soai://mail"


def build_mail_message_resource_uri(
    message_id: str,
    *,
    part_id: str | None,
    max_chars: int,
    offset_chars: int,
) -> str:
    return build_resource_uri(
        base_uri=MAIL_RESOURCE_URI,
        path=f"/messages/{message_id}",
        query_items=(
            ("max_chars", max_chars),
            ("offset_chars", offset_chars),
            ("part_id", part_id),
        ),
    )


def build_mail_folder_head_resource_uri(
    folder_id: str,
    *,
    limit: int,
    order_by: str,
    order_direction: str,
    query: str | None,
) -> str:
    return build_resource_uri(
        base_uri=MAIL_RESOURCE_URI,
        path=f"/folders/{folder_id}/head",
        query_items=(
            ("limit", limit),
            ("order_by", order_by),
            ("order_direction", order_direction),
            ("query", query),
        ),
    )
