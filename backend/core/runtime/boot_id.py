"""SoAI - Process boot identity provider [backend/core/runtime/boot_id.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from functools import cache

__all__ = ("get_boot_id",)


@cache
def get_boot_id() -> str:
    return f"boot_{uuid.uuid4().hex[:16]}"
