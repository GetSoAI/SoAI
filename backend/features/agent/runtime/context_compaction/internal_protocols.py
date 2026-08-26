"""SoAI - Context compaction internal protocols [backend/features/agent/runtime/context_compaction/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("TruncateLineProtocol",)


class TruncateLineProtocol(Protocol):
    def __call__(self, text: str, *, max_chars: int = 240) -> str: ...
