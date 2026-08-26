"""SoAI - Agent turn optional text normalization [backend/database/repositories/users/agent_turn_text_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("normalize_agent_turn_optional_text",)


def normalize_agent_turn_optional_text(value: JSONValue) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
