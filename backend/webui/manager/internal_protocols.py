"""SoAI - WebUI manager internal protocols [backend/webui/manager/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.runtime.protocols import RequestProtocol

__all__ = ("AuthFailureLoggerProtocol",)


class AuthFailureLoggerProtocol(Protocol):
    async def __call__(
        self,
        request: RequestProtocol,
        reason: str,
        client_ip: str | None,
        *,
        fingerprint: str | None,
        throttled: bool,
        retry_at: int | None,
    ) -> None: ...
