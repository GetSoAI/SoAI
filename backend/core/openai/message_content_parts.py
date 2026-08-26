"""SoAI - OpenAI chat message content part iteration [backend/core/openai/message_content_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Iterator

from core.types.json import JSONDict, is_json_dict

__all__ = ("iter_message_content_parts",)


def iter_message_content_parts(messages: Iterable[JSONDict]) -> Iterator[JSONDict]:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if is_json_dict(part):
                yield part
