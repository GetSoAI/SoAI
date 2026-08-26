"""SoAI - Core types protocols [backend/core/types/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, AsyncContextManager, Protocol

import httpx2

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type HttpDataPayload = Mapping[str, JSONValue]
    type HttpFilesPayload = (
        Mapping[str, tuple[str, bytes] | tuple[str, bytes, str]]
        | Sequence[tuple[str, tuple[str, bytes] | tuple[str, bytes, str]]]
    )

__all__ = ("HttpClientProtocol",)


class HttpClientProtocol(Protocol):
    async def aclose(self) -> None: ...

    async def request(
        self,
        method: str,
        url: str,
        *,
        follow_redirects: bool = ...,
        timeout: float | None = ...,
        headers: Mapping[str, str] | None = ...,
        params: Mapping[str, str | int] | None = ...,
        json: JSONValue | None = ...,
        data: HttpDataPayload | None = ...,
        files: HttpFilesPayload | None = ...,
    ) -> httpx2.Response: ...

    async def get(
        self,
        url: str,
        *,
        follow_redirects: bool = ...,
        timeout: float | None = ...,
        headers: Mapping[str, str] | None = ...,
        params: Mapping[str, str | int] | None = ...,
    ) -> httpx2.Response: ...

    async def head(
        self,
        url: str,
        *,
        follow_redirects: bool = ...,
        timeout: float | None = ...,
        headers: Mapping[str, str] | None = ...,
        params: Mapping[str, str | int] | None = ...,
    ) -> httpx2.Response: ...

    async def post(
        self,
        url: str,
        *,
        follow_redirects: bool = ...,
        timeout: float | None = ...,
        headers: Mapping[str, str] | None = ...,
        params: Mapping[str, str | int] | None = ...,
        json: JSONValue | None = ...,
        data: HttpDataPayload | None = ...,
        files: HttpFilesPayload | None = ...,
    ) -> httpx2.Response: ...

    def stream(
        self,
        method: str,
        url: str,
        *,
        follow_redirects: bool = ...,
        timeout: float | None = ...,
        headers: Mapping[str, str] | None = ...,
        params: Mapping[str, str | int] | None = ...,
        json: JSONValue | None = ...,
        data: HttpDataPayload | None = ...,
        files: HttpFilesPayload | None = ...,
        extensions: Mapping[str, str] | None = ...,
    ) -> AsyncContextManager[httpx2.Response]: ...
