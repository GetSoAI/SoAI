"""SoAI - Raw SoAI path token validation [backend/core/workspaces/soai_path_text_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.workspaces.soai_path_link_codec import extract_soai_path_tokens

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("validate_no_raw_soai_path_tokens",)


def validate_no_raw_soai_path_tokens(content: str | list[JSONDict]) -> None:
    if isinstance(content, str):
        if extract_soai_path_tokens(content):
            raise ValidationError("Messages cannot persist raw SoAI path tokens.")
        return
    for part in content:
        if part.get("type") != "text":
            continue
        text_value = part.get("text")
        if isinstance(text_value, str) and extract_soai_path_tokens(text_value):
            raise ValidationError("Messages cannot persist raw SoAI path tokens.")
