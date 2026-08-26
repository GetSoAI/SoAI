"""SoAI - AI Horde image response parsing [backend/mcp/tools/generate_image_horde_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.base64_values import (
    decode_base64_ascii,
    extract_base64_data_payload,
)
from core.types.json_value import filter_json_dict_list
from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_http import read_image_provider_json

if TYPE_CHECKING:
    import httpx2

    from core.types.json import JSONDict

__all__ = (
    "decode_horde_generation_image",
    "horde_status_is_faulted",
    "raise_for_terminal_horde_status_without_image",
    "read_horde_json_response",
    "require_horde_generation_id",
)


async def read_horde_json_response(response: httpx2.Response, *, field: str) -> JSONDict:
    return await read_image_provider_json(response, field=field)


def require_horde_generation_id(payload: JSONDict) -> str:
    generation_id = payload.get("id")
    if not isinstance(generation_id, str) or not generation_id.strip():
        raise MCPToolError(-32603, "Image generation provider did not return a request id.")
    return generation_id.strip()


def decode_horde_generation_image(status_payload: JSONDict) -> bytes | None:
    generations = filter_json_dict_list(status_payload.get("generations"))
    if not generations:
        return None
    generation = generations[0]
    image_value = generation.get("img")
    if not isinstance(image_value, str) or not image_value.strip():
        raise MCPToolError(-32603, "Image generation provider returned an invalid image payload.")
    if image_value.strip().lower().startswith(("http://", "https://")):
        raise MCPToolError(-32603, "Image generation provider returned a hosted image URL.")
    encoded = extract_base64_data_payload(image_value.strip())
    try:
        return decode_base64_ascii(
            encoded,
            error_message="Image generation provider returned invalid base64 image data.",
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception


def raise_for_terminal_horde_status_without_image(status_payload: JSONDict) -> None:
    possible = status_payload.get("is_possible")
    if isinstance(possible, bool) and not possible:
        raise MCPToolError(-32603, "Image generation provider marked the request as impossible.")
    done = status_payload.get("done")
    if isinstance(done, bool) and done:
        raise MCPToolError(-32603, "Image generation provider completed without an image.")


def horde_status_is_faulted(status_payload: JSONDict) -> bool:
    faulted = status_payload.get("faulted")
    return bool(faulted) if isinstance(faulted, bool) else False
