"""SoAI - OpenAI API authentication protection states [backend/core/auth/openai_protection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import StrEnum

__all__ = ("OpenAIProtectionState",)


class OpenAIProtectionState(StrEnum):
    OPEN = "open"
    REQUIRED = "required"
    INDETERMINATE = "indeterminate"
