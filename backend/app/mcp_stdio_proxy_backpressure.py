"""SoAI - MCP stdio proxy backpressure [backend/app/mcp_stdio_proxy_backpressure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "join_inbound_queue",
    "put_inbound_payload",
    "put_stdout_line",
)


async def put_stdout_line(stdout_queue: asyncio.Queue[str], line: str) -> None:
    try:
        await asyncio.wait_for(
            stdout_queue.put(line),
            timeout=LOCAL_IO_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise StateError("MCP stdio proxy stdout is blocked.") from exception


async def put_inbound_payload(
    inbound_queue: asyncio.Queue[JSONDict | None],
    payload: JSONDict | None,
) -> None:
    try:
        await asyncio.wait_for(
            inbound_queue.put(payload),
            timeout=LOCAL_IO_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise StateError("MCP stdio proxy inbound queue is blocked.") from exception


async def join_inbound_queue(
    inbound_queue: asyncio.Queue[JSONDict | None],
) -> None:
    try:
        await asyncio.wait_for(
            inbound_queue.join(),
            timeout=INTERACTIVE_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise StateError("MCP stdio proxy inbound queue join timed out.") from exception
