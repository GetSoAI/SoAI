"""SoAI - Async parameter cache for model parameters [backend/models/parameters/cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import TYPE_CHECKING

from core.types.json_value import copy_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("AsyncParameterCache",)


class AsyncParameterCache:

    def __init__(self, max_size: int = 2000) -> None:
        self.max_size = max_size
        self.cache: OrderedDict[str, tuple[JSONDict, int]] = OrderedDict()
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> tuple[JSONDict, int] | None:
        async with self.lock:
            if key in self.cache:
                data, version = self.cache[key]
                self.cache.move_to_end(key)
                return (copy_json_dict(data), version)
            return None

    async def put(self, key: str, value: JSONDict, version: int) -> None:
        async with self.lock:
            self.cache[key] = (copy_json_dict(value), version)
            self.cache.move_to_end(key)
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    async def invalidate(self, key: str) -> None:
        async with self.lock:
            self.cache.pop(key, None)
