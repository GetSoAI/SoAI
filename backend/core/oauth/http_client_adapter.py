"""SoAI - HTTP client adapter for core OAuth engine [backend/core/oauth/http_client_adapter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import override

import httpx2

from core.errors.exceptions import ValidationError
from core.oauth.protocols import OAuthHTTPClientProtocol, OAuthHTTPResponseProtocol
from core.types.json import JSONValue
from core.types.json_value import is_json_value

__all__ = ("OAuthHTTPClientAdapter",)


class _OAuthHTTPResponseAdapter(OAuthHTTPResponseProtocol):
    __slots__ = ("_response",)

    def __init__(self, response: httpx2.Response) -> None:
        self._response = response

    @property
    @override
    def status_code(self) -> int:
        return int(self._response.status_code)

    @property
    @override
    def headers(self) -> Mapping[str, str]:
        return dict(self._response.headers.items())

    @override
    def json(self) -> JSONValue:
        payload = self._response.json()
        if not is_json_value(payload):
            raise ValidationError("OAuth response body is not valid JSON.")
        return payload

    @property
    @override
    def text(self) -> str:
        return self._response.text


class OAuthHTTPClientAdapter(OAuthHTTPClientProtocol):
    __slots__ = ("_client",)

    def __init__(self, client: httpx2.AsyncClient) -> None:
        self._client = client

    @override
    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> OAuthHTTPResponseProtocol:
        response = await self._client.get(url, headers=headers, timeout=timeout)
        return _OAuthHTTPResponseAdapter(response)

    @override
    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json: Mapping[str, JSONValue] | None = None,
        timeout: float | None = None,
    ) -> OAuthHTTPResponseProtocol:
        response = await self._client.post(
            url,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
        )
        return _OAuthHTTPResponseAdapter(response)
