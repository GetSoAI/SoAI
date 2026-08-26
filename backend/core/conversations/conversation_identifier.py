"""SoAI - Canonical conversation identifier contract [backend/core/conversations/conversation_identifier.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

CONVERSATION_ID_PATTERN_TEXT = r"^conv_[a-f0-9\-]+$"


def parse_conversation_identifier(value: str) -> str | None:
    candidate = value.strip()
    if re.fullmatch(CONVERSATION_ID_PATTERN_TEXT, candidate, re.ASCII) is None:
        return None
    return candidate


__all__ = (
    "CONVERSATION_ID_PATTERN_TEXT",
    "parse_conversation_identifier",
)
