"""SoAI - API runtime client host resolution [backend/features/api/runtime/client_host.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.runtime.proxy_headers import extract_real_client_ip
from core.runtime.state_access import read_request_state_value

__all__ = ("resolve_client_host",)


def resolve_client_host(request: Request, default: str = "unknown") -> str:
    stored = read_request_state_value(request, "client_host", str)
    if isinstance(stored, str) and stored:
        return stored
    extracted = extract_real_client_ip(request)
    if extracted:
        return extracted
    client = request.client
    host = client.host if client else None
    return host or default
