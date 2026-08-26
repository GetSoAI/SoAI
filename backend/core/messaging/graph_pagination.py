"""SoAI - Meta Graph pagination contracts [backend/core/messaging/graph_pagination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("read_graph_next_cursor",)


def read_graph_next_cursor(payload: JSONDict, *, response_label: str) -> str | None:
    paging = coerce_json_dict(payload.get("paging"))
    if paging is None or coerce_optional_trimmed_str(paging.get("next")) is None:
        return None
    cursors = coerce_json_dict(paging.get("cursors"))
    if cursors is None:
        raise ValidationError(f"{response_label} pagination is invalid.")
    after = coerce_optional_trimmed_str(cursors.get("after"))
    if after is None:
        raise ValidationError(f"{response_label} pagination cursor is invalid.")
    return after
