"""SoAI - Async cancellation propagation helpers [backend/core/errors/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import NoReturn

__all__ = ("raise_cancelled_error",)


def raise_cancelled_error(exception: asyncio.CancelledError) -> NoReturn:
    raise exception
