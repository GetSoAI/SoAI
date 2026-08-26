"""SoAI - OAuth engine protocols [backend/core/oauth/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from typing import Protocol

from core.types.json import JSONValue

__all__ = (
    "OAuthHTTPClientProtocol",
    "OAuthHTTPResponseProtocol",
    "OAuthRuntimeUrlValidator",
)


class OAuthHTTPResponseProtocol(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self) -> JSONValue: ...

    @property
    def text(self) -> str: ...


class OAuthHTTPClientProtocol(Protocol):
    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> OAuthHTTPResponseProtocol: ...

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json: Mapping[str, JSONValue] | None = None,
        timeout: float | None = None,
    ) -> OAuthHTTPResponseProtocol: ...


class OAuthRuntimeUrlValidator(Protocol):
    def __call__(self, url: str, source: str) -> Awaitable[None]: ...
