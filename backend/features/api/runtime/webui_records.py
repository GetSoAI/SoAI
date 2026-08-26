"""SoAI - WebUI record helpers [backend/features/api/runtime/webui_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, overload

from core.errors.exceptions import NotFoundError
from features.api.runtime.errors import raise_not_found

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "webui_fetch_or_404",
    "webui_require_true_or_404",
)


@overload
async def webui_fetch_or_404(
    request: RequestProtocol,
    coro: Awaitable[JSONDict | None],
    *,
    message: str,
) -> JSONDict: ...


@overload
async def webui_fetch_or_404(
    request: RequestProtocol,
    coro: Awaitable[JSONValue | None],
    *,
    message: str,
) -> JSONValue: ...


async def webui_fetch_or_404(
    request: RequestProtocol,
    coro: Awaitable[JSONValue | None],
    *,
    message: str,
) -> JSONValue:
    result = await coro
    if result is None:
        raise NotFoundError(message, trace_id=request.state.context.trace_id)
    return result


async def webui_require_true_or_404(
    request: RequestProtocol,
    coro: Awaitable[bool],
    *,
    message: str,
) -> None:
    ok = await coro
    if not ok:
        raise_not_found(request, message)
