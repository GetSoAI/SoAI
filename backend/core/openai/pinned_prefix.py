"""SoAI - OpenAI pinned-prefix message helpers [backend/core/openai/pinned_prefix.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from core.openai.chat_role_sets import OPENAI_PINNED_ROLES

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "split_leading_pinned_prefix",
    "strip_leading_pinned_prefix",
)


def split_leading_pinned_prefix(
    messages: Sequence[JSONDict],
    *,
    stop_before: Callable[[JSONDict], bool] | None = None,
) -> tuple[list[JSONDict], list[JSONDict]]:
    pinned_prefix: list[JSONDict] = []
    remaining_messages: list[JSONDict] = []
    pinned_prefix_complete = False
    for message in messages:
        normalized = dict(message)
        if pinned_prefix_complete:
            remaining_messages.append(normalized)
            continue
        if stop_before is not None and stop_before(normalized):
            pinned_prefix_complete = True
            remaining_messages.append(normalized)
            continue
        role_value = normalized.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role in OPENAI_PINNED_ROLES:
            pinned_prefix.append(normalized)
            continue
        pinned_prefix_complete = True
        remaining_messages.append(normalized)
    return (pinned_prefix, remaining_messages)


def strip_leading_pinned_prefix(messages: Sequence[JSONDict]) -> list[JSONDict]:
    return split_leading_pinned_prefix(messages)[1]
