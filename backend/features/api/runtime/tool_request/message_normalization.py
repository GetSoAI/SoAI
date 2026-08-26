"""SoAI - MCP tool request message normalization [backend/features/api/runtime/tool_request/message_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.conversation_request_normalization import (
    normalize_conv_id_and_messages_payload,
)
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict

__all__ = ("normalize_conv_id_and_messages",)


def normalize_conv_id_and_messages(
    request: RequestProtocol,
    request_json: JSONDict,
) -> tuple[str | None, list[JSONDict]]:
    try:
        return normalize_conv_id_and_messages_payload(request_json)
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
