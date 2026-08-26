"""SoAI - MCP stdio proxy HTTP helpers [backend/app/mcp_stdio_proxy_http.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import StateError
from core.mcp.mcp_2025_11_25 import (
    MCP_PROTOCOL_VERSION_HEADER,
    MCP_SESSION_ID_HEADER,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.validation.record_fields import require_json_object

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "delete_session",
    "perform_whoami_handshake",
    "post_json",
)


async def perform_whoami_handshake(
    client: httpx2.AsyncClient,
    *,
    endpoint: str,
    token: str,
    expected_user_id: int,
) -> tuple[int, str]:
    response = await client.get(
        f"{endpoint}/whoami",
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        raise StateError("MCP whoami handshake failed.")
    parsed = require_json_object(
        parse_json_value(response.text, field="whoami response"),
        label="whoami response",
        build_error=StateError,
        invalid_message="Invalid whoami response.",
    )
    user_id_value = parsed.get("user_id")
    username_value = parsed.get("username")
    if not isinstance(user_id_value, int):
        raise StateError("Invalid whoami response.")
    if not isinstance(username_value, str) or not username_value:
        raise StateError("Invalid whoami response.")
    if user_id_value != expected_user_id:
        raise StateError("MCP token does not match SOAI_MCP_USER_ID.")
    return (user_id_value, username_value)


async def post_json(
    client: httpx2.AsyncClient,
    url: str,
    *,
    token: str,
    session_id: str | None,
    protocol_version: str,
    payload: JSONDict,
) -> httpx2.Response:
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        MCP_PROTOCOL_VERSION_HEADER: protocol_version,
    }
    if session_id is not None:
        headers[MCP_SESSION_ID_HEADER] = session_id
    body = serialize_json_compact_stable_strict(payload)
    return await client.post(
        url,
        content=body,
        headers=headers,
    )


async def delete_session(
    client: httpx2.AsyncClient,
    *,
    endpoint: str,
    token: str,
    session_id: str,
) -> None:
    await client.delete(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            MCP_SESSION_ID_HEADER: session_id,
        },
    )
