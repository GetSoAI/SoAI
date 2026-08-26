"""SoAI - WebUI request client IP extraction helpers [backend/webui/manager/request_client_ip.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.protocols import RequestProtocol
from core.runtime.state_access import read_request_state_value

__all__ = ("resolve_request_client_ip",)


def resolve_request_client_ip(request: RequestProtocol) -> str:
    stored_client_host = read_request_state_value(request, "client_host", str)
    client = request.client
    return str(stored_client_host or (client.host if client else "") or "")
