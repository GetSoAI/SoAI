"""SoAI - Automatic1111 image generation provider [backend/mcp/tools/generate_image_automatic1111.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.base64_values import (
    decode_base64_ascii,
    encode_base64_ascii,
    extract_base64_data_payload,
)
from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_config import Automatic1111ImageSettings
from mcp.tools.generate_image_http import (
    build_image_provider_http_error,
    read_image_provider_json,
)
from mcp.tools.generate_image_types import (
    ImageGenerationDeadline,
    ImageGenerationRequest,
    ImageGenerationResult,
)

if TYPE_CHECKING:
    import httpx2

    from core.types.json import JSONDict, JSONValue

__all__ = ("generate_with_automatic1111",)


async def generate_with_automatic1111(
    *,
    http_client: httpx2.AsyncClient,
    base_url: str,
    settings: Automatic1111ImageSettings,
    request: ImageGenerationRequest,
    deadline: ImageGenerationDeadline,
    extensions: dict[str, str] | None,
) -> ImageGenerationResult:
    response = await http_client.post(
        f"{base_url}/sdapi/v1/txt2img",
        json=_build_payload(settings, request),
        headers=_build_headers(settings),
        timeout=deadline.request_timeout(),
        extensions=extensions,
    )
    if int(response.status_code) < 200 or int(response.status_code) >= 300:
        raise MCPToolError(-32603, await build_image_provider_http_error(response))
    payload = await read_image_provider_json(response, field="Automatic1111 txt2img response")
    image_bytes = _decode_first_image(payload)
    return ImageGenerationResult(
        provider="automatic1111",
        image_bytes=image_bytes,
        width=request.width,
        height=request.height,
        seed=request.seed,
    )


def _build_payload(
    settings: Automatic1111ImageSettings,
    request: ImageGenerationRequest,
) -> JSONDict:
    payload: JSONDict = dict(settings.extra_params)
    payload.update(
        {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "cfg_scale": request.cfg_scale,
            "batch_size": 1,
            "n_iter": 1,
        },
    )
    if request.seed is not None:
        payload["seed"] = request.seed
    if settings.sampler_name is not None:
        payload["sampler_name"] = settings.sampler_name
    if settings.scheduler is not None:
        payload["scheduler"] = settings.scheduler
    return payload


def _build_headers(settings: Automatic1111ImageSettings) -> dict[str, str]:
    if settings.basic_auth is None:
        return {}
    credentials = encode_base64_ascii(settings.basic_auth.encode("utf-8"))
    return {"Authorization": f"Basic {credentials}"}


def _decode_first_image(payload: JSONDict) -> bytes:
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise MCPToolError(-32603, "Image generation provider returned no images.")
    first_image: JSONValue = images[0]
    if not isinstance(first_image, str) or not first_image.strip():
        raise MCPToolError(-32603, "Image generation provider returned an invalid image payload.")
    encoded = extract_base64_data_payload(first_image.strip())
    try:
        return decode_base64_ascii(
            encoded,
            error_message="Image generation provider returned invalid base64 image data.",
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
