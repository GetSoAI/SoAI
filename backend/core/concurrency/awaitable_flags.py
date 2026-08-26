"""SoAI - Awaitable flag resolution helpers [backend/core/concurrency/awaitable_flags.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable

__all__ = ("resolve_bool_flag",)


async def resolve_bool_flag(value: bool | Awaitable[bool]) -> bool:
    if isinstance(value, bool):
        return value
    return bool(await value)
