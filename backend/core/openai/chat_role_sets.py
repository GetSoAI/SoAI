"""SoAI - OpenAI chat role sets [backend/core/openai/chat_role_sets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

OPENAI_ALLOWED_ROLES: frozenset[str] = frozenset(
    ("system", "developer", "user", "assistant", "tool", "function"),
)
OPENAI_PINNED_ROLES: frozenset[str] = frozenset(("system", "developer"))
