"""SoAI - Core terminal request models shared between protocols and implementations [backend/core/terminal/requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ("CreatePTYSessionRequest",)


@dataclass(frozen=True, slots=True)
class CreatePTYSessionRequest:
    session_id: str
    cols: int
    rows: int
    user_id: int = 0
    shell: str | None = None
    output_callback: Callable[[bytes], None] | None = None
    exit_callback: Callable[[str, int], None] | None = None
    busy_callback: Callable[[str, bool], None] | None = None
