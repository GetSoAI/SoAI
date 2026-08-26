"""SoAI - MCP server pagination cursor codec [backend/mcp/server/handlers/pagination_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.serialization.base64_values import (
    decode_base64_ascii_urlsafe,
    encode_base64_urlsafe_ascii,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.validation.coercion import coerce_non_negative_int_from_numberish

__all__ = (
    "MCPPaginationCodec",
    "MCPPaginationCodecDependencies",
)


@dataclass(frozen=True, slots=True)
class MCPPaginationCodecDependencies:
    default_page_size: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPPaginationCodecDependencies",
            default_page_size=self.default_page_size,
        )
        if isinstance(self.default_page_size, bool) or (
            not isinstance(self.default_page_size, int)
        ):
            raise ValidationError("default_page_size must be an integer.")
        if self.default_page_size < 1:
            raise ValidationError("default_page_size must be >= 1.")


class MCPPaginationCodec:
    def __init__(self, deps: MCPPaginationCodecDependencies) -> None:
        self._default_page_size = deps.default_page_size

    def encode_pagination_cursor(self, offset: int) -> str:
        payload = serialize_json_compact_stable_strict({"offset": offset}).encode()
        return encode_base64_urlsafe_ascii(payload)

    def decode_pagination_cursor(self, cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            decoded = decode_base64_ascii_urlsafe(
                cursor,
                error_message="Invalid pagination cursor.",
            )
            data = parse_json_value(decoded)
            if not isinstance(data, dict):
                return 0
            return coerce_non_negative_int_from_numberish(data.get("offset", 0))
        except (ValueError, TypeError, ValidationError, KeyError):
            return 0

    def paginate_list[PageItem](
        self,
        items: list[PageItem],
        cursor: str | None,
    ) -> tuple[list[PageItem], str | None]:
        offset = self.decode_pagination_cursor(cursor)
        page_size = self._default_page_size
        end_index = offset + page_size
        page = items[offset:end_index]
        next_cursor: str | None = None
        if end_index < len(items):
            next_cursor = self.encode_pagination_cursor(end_index)
        return (page, next_cursor)
