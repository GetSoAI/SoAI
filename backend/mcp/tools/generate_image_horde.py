"""SoAI - AI Horde image generation provider client [backend/mcp/tools/generate_image_horde.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import httpx2

from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.timing.epoch import epoch_seconds_float
from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_horde_constants import DEFAULT_HORDE_PROVIDER
from mcp.tools.generate_image_horde_responses import (
    decode_horde_generation_image,
    horde_status_is_faulted,
    raise_for_terminal_horde_status_without_image,
    read_horde_json_response,
    require_horde_generation_id,
)
from mcp.tools.generate_image_http import build_image_provider_http_error
from mcp.tools.generate_image_types import (
    ImageGenerationDeadline,
    ImageGenerationRequest,
    ImageGenerationResult,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "DEFAULT_HORDE_PROVIDER",
    "build_horde_generation_payload",
    "generate_with_horde",
    "poll_horde_result",
    "submit_horde_request",
)

_CLIENT_AGENT = "SoAI:generate_image:1.0"


def build_horde_generation_payload(*, request: ImageGenerationRequest, model: str) -> JSONDict:
    params: JSONDict = {
        "width": request.width,
        "height": request.height,
        "n": 1,
        "steps": request.steps,
        "cfg_scale": request.cfg_scale,
    }
    if request.seed is not None:
        params["seed"] = str(int(request.seed))
    return {
        "prompt": _build_horde_prompt(request),
        "params": params,
        "models": [model],
        "nsfw": False,
        "trusted_workers": False,
        "censor_nsfw": True,
        "r2": False,
        "shared": False,
    }


async def generate_with_horde(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    base_url: str,
    api_key: str,
    model: str,
    request: ImageGenerationRequest,
    deadline: ImageGenerationDeadline,
    poll_interval_sec: float,
    extensions: dict[str, str] | None,
) -> ImageGenerationResult:
    payload = build_horde_generation_payload(request=request, model=model)
    generation_id = await submit_horde_request(
        utility_tools=utility_tools,
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        deadline=deadline,
        extensions=extensions,
    )
    image_bytes = await poll_horde_result(
        utility_tools=utility_tools,
        base_url=base_url,
        api_key=api_key,
        generation_id=generation_id,
        deadline=deadline,
        poll_interval_sec=poll_interval_sec,
        extensions=extensions,
    )
    return ImageGenerationResult(
        provider=DEFAULT_HORDE_PROVIDER,
        image_bytes=image_bytes,
        width=request.width,
        height=request.height,
        seed=request.seed,
    )


async def submit_horde_request(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    base_url: str,
    api_key: str,
    payload: JSONDict,
    deadline: ImageGenerationDeadline,
    extensions: dict[str, str] | None,
) -> str:
    http_client = utility_tools.http_client
    if http_client is None:
        raise MCPToolError(-32603, "HTTP client is not available")
    while deadline.remaining() > 0.0:
        reserved = await utility_tools.generate_image_horde_rate_gate.reserve(
            base_url=base_url,
            api_key=api_key,
            deadline_monotonic=deadline.monotonic,
        )
        if not reserved:
            break
        response = await http_client.post(
            f"{base_url}/api/v2/generate/async",
            json=payload,
            headers=_build_horde_headers(api_key),
            timeout=deadline.request_timeout(),
            extensions=extensions,
        )
        if int(response.status_code) == 429:
            retry_delay_sec = _resolve_rate_limit_retry_delay(
                response,
                float(CONTROL_TIMEOUT_SEC),
            )
            if time.monotonic() + retry_delay_sec < deadline.monotonic:
                await asyncio.sleep(retry_delay_sec)
                continue
        if int(response.status_code) < 200 or int(response.status_code) >= 300:
            raise MCPToolError(-32603, await build_image_provider_http_error(response))
        response_payload = await read_horde_json_response(
            response,
            field="AI Horde generation response",
        )
        return require_horde_generation_id(response_payload)
    raise MCPToolError(-32603, "Image generation provider timed out while processing the request.")


async def poll_horde_result(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    base_url: str,
    api_key: str,
    generation_id: str,
    deadline: ImageGenerationDeadline,
    poll_interval_sec: float,
    extensions: dict[str, str] | None,
) -> bytes:
    http_client = utility_tools.http_client
    if http_client is None:
        raise MCPToolError(-32603, "HTTP client is not available")
    while deadline.remaining() > 0.0:
        reserved = await utility_tools.generate_image_horde_rate_gate.reserve(
            base_url=base_url,
            api_key=api_key,
            deadline_monotonic=deadline.monotonic,
        )
        if not reserved:
            break
        response = await http_client.get(
            f"{base_url}/api/v2/generate/status/{generation_id}",
            headers=_build_horde_headers(api_key),
            timeout=deadline.request_timeout(),
            extensions=extensions,
        )
        if int(response.status_code) < 200 or int(response.status_code) >= 300:
            if int(response.status_code) == 429:
                retry_delay_sec = _resolve_rate_limit_retry_delay(response, poll_interval_sec)
                if time.monotonic() + retry_delay_sec < deadline.monotonic:
                    await asyncio.sleep(retry_delay_sec)
                    continue
            raise MCPToolError(-32603, await build_image_provider_http_error(response))
        status_payload = await read_horde_json_response(response, field="AI Horde status response")
        image_bytes = decode_horde_generation_image(status_payload)
        if image_bytes is not None:
            return image_bytes
        raise_for_terminal_horde_status_without_image(status_payload)
        if horde_status_is_faulted(status_payload):
            raise MCPToolError(-32603, "Image generation provider marked the request as faulted.")
        await asyncio.sleep(
            _resolve_status_poll_delay(status_payload, poll_interval_sec, deadline.monotonic),
        )
    raise MCPToolError(-32603, "Image generation provider timed out while processing the request.")


def _build_horde_headers(api_key: str) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Client-Agent": _CLIENT_AGENT,
    }


def _build_horde_prompt(request: ImageGenerationRequest) -> str:
    if not request.negative_prompt:
        return request.prompt
    return f"{request.prompt} ### {request.negative_prompt}"


def _resolve_rate_limit_retry_delay(response: httpx2.Response, poll_interval_sec: float) -> float:
    reset_value = response.headers.get("x-ratelimit-reset")
    if isinstance(reset_value, str) and reset_value.strip():
        try:
            reset_epoch_sec = float(reset_value.strip())
        except ValueError:
            reset_epoch_sec = 0.0
        if reset_epoch_sec > 0.0:
            return max(
                float(poll_interval_sec),
                min(90.0, reset_epoch_sec - epoch_seconds_float() + 1.0),
            )
    retry_after_value = response.headers.get("retry-after")
    if isinstance(retry_after_value, str) and retry_after_value.strip():
        try:
            retry_after_sec = float(retry_after_value.strip())
        except ValueError:
            retry_after_sec = 0.0
        if retry_after_sec > 0.0:
            return max(float(poll_interval_sec), min(90.0, retry_after_sec + 1.0))
    return max(float(poll_interval_sec), 60.0)


def _resolve_status_poll_delay(
    status_payload: JSONDict,
    poll_interval_sec: float,
    deadline_monotonic: float,
) -> float:
    wait_time = status_payload.get("wait_time")
    queue_delay = float(poll_interval_sec)
    if isinstance(wait_time, int | float) and wait_time > 0:
        queue_delay = max(queue_delay, min(60.0, float(wait_time) / 8.0))
    remaining = deadline_monotonic - time.monotonic()
    return max(0.25, min(queue_delay, max(0.25, remaining)))
