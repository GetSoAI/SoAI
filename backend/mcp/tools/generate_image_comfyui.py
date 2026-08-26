"""SoAI - ComfyUI image generation provider [backend/mcp/tools/generate_image_comfyui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx2

from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_comfyui_history import (
    extract_comfyui_history_image_reference,
)
from mcp.tools.generate_image_config import ComfyUIImageSettings
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
    from core.types.json import JSONDict, JSONValue

__all__ = ("generate_with_comfyui",)


async def generate_with_comfyui(
    *,
    http_client: httpx2.AsyncClient,
    base_url: str,
    settings: ComfyUIImageSettings,
    request: ImageGenerationRequest,
    deadline: ImageGenerationDeadline,
    poll_interval_sec: float,
    extensions: dict[str, str] | None,
) -> ImageGenerationResult:
    workflow = _build_workflow(settings, request)
    response = await http_client.post(
        f"{base_url}/prompt",
        json={"prompt": workflow},
        headers=_build_headers(settings),
        timeout=deadline.request_timeout(),
        extensions=extensions,
    )
    if int(response.status_code) < 200 or int(response.status_code) >= 300:
        raise MCPToolError(-32603, await build_image_provider_http_error(response))
    queued = await read_image_provider_json(response, field="ComfyUI prompt response")
    prompt_id = _require_prompt_id(queued)
    try:
        image_reference = await _poll_history(
            http_client=http_client,
            base_url=base_url,
            settings=settings,
            prompt_id=prompt_id,
            deadline=deadline,
            poll_interval_sec=poll_interval_sec,
            extensions=extensions,
        )
    except asyncio.CancelledError:
        await _delete_prompt(
            http_client=http_client,
            base_url=base_url,
            settings=settings,
            prompt_id=prompt_id,
            deadline=deadline,
            extensions=extensions,
        )
        raise
    except MCPToolError as exception:
        if _is_provider_timeout_error(exception):
            await _delete_prompt(
                http_client=http_client,
                base_url=base_url,
                settings=settings,
                prompt_id=prompt_id,
                deadline=deadline,
                extensions=extensions,
            )
        raise
    image_bytes = await _fetch_image(
        http_client=http_client,
        base_url=base_url,
        settings=settings,
        image_reference=image_reference,
        deadline=deadline,
        extensions=extensions,
    )
    return ImageGenerationResult(
        provider="comfyui",
        image_bytes=image_bytes,
        width=request.width,
        height=request.height,
        seed=request.seed,
    )


def _build_workflow(settings: ComfyUIImageSettings, request: ImageGenerationRequest) -> JSONDict:
    if not settings.workflow:
        raise MCPToolError(-32602, "ComfyUI generation requires COMFYUI.WORKFLOW_JSON.")
    workflow = copy.deepcopy(settings.workflow)
    if not isinstance(workflow, dict):
        raise MCPToolError(-32602, "ComfyUI workflow must be a JSON object.")
    for mapping in settings.workflow_nodes:
        _apply_mapping(workflow, mapping, settings, request)
    return workflow


def _apply_mapping(
    workflow: JSONDict,
    mapping: JSONDict,
    settings: ComfyUIImageSettings,
    request: ImageGenerationRequest,
) -> None:
    node_id = _required_text(mapping, "node_id")
    field_name = _required_text(mapping, "field")
    value_name = _required_text(mapping, "value")
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        raise MCPToolError(-32602, f"ComfyUI workflow node {node_id} does not exist.")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        raise MCPToolError(-32602, f"ComfyUI workflow node {node_id} has no inputs.")
    inputs[field_name] = _resolve_mapping_value(value_name, settings, request, mapping)


def _resolve_mapping_value(
    value_name: str,
    settings: ComfyUIImageSettings,
    request: ImageGenerationRequest,
    mapping: JSONDict,
) -> JSONValue:
    if value_name == "prompt":
        return request.prompt
    if value_name == "negative_prompt":
        return request.negative_prompt
    if value_name == "width":
        return request.width
    if value_name == "height":
        return request.height
    if value_name == "steps":
        return request.steps
    if value_name == "cfg_scale":
        return request.cfg_scale
    if value_name == "seed":
        return request.seed if request.seed is not None else 0
    if value_name == "model":
        return settings.model or ""
    if value_name == "literal":
        return mapping.get("literal")
    raise MCPToolError(-32602, f"Unsupported ComfyUI workflow mapping value: {value_name}.")


async def _poll_history(
    *,
    http_client: httpx2.AsyncClient,
    base_url: str,
    settings: ComfyUIImageSettings,
    prompt_id: str,
    deadline: ImageGenerationDeadline,
    poll_interval_sec: float,
    extensions: dict[str, str] | None,
) -> JSONDict:
    while deadline.remaining() > 0.0:
        response = await http_client.get(
            f"{base_url}/history/{prompt_id}",
            headers=_build_headers(settings),
            timeout=deadline.request_timeout(),
            extensions=extensions,
        )
        if int(response.status_code) < 200 or int(response.status_code) >= 300:
            raise MCPToolError(-32603, await build_image_provider_http_error(response))
        history = await read_image_provider_json(response, field="ComfyUI history response")
        image_reference = extract_comfyui_history_image_reference(history, settings, prompt_id)
        if image_reference is not None:
            return image_reference
        await _sleep(poll_interval_sec, deadline.monotonic)
    raise MCPToolError(-32603, "Image generation provider timed out while processing the request.")


async def _fetch_image(
    *,
    http_client: httpx2.AsyncClient,
    base_url: str,
    settings: ComfyUIImageSettings,
    image_reference: JSONDict,
    deadline: ImageGenerationDeadline,
    extensions: dict[str, str] | None,
) -> bytes:
    query = urlencode(
        {
            "filename": _required_text(image_reference, "filename"),
            "subfolder": _optional_text(image_reference, "subfolder") or "",
            "type": _optional_text(image_reference, "type") or "output",
        },
    )
    response = await http_client.get(
        f"{base_url}/view?{query}",
        headers=_build_headers(settings),
        timeout=deadline.request_timeout(),
        extensions=extensions,
    )
    if int(response.status_code) < 200 or int(response.status_code) >= 300:
        raise MCPToolError(-32603, await build_image_provider_http_error(response))
    return await response.aread()


async def _delete_prompt(
    *,
    http_client: httpx2.AsyncClient,
    base_url: str,
    settings: ComfyUIImageSettings,
    prompt_id: str,
    deadline: ImageGenerationDeadline,
    extensions: dict[str, str] | None,
) -> None:
    response = await http_client.post(
        f"{base_url}/queue",
        json={"delete": [prompt_id]},
        headers=_build_headers(settings),
        timeout=deadline.request_timeout(),
        extensions=extensions,
    )
    if int(response.status_code) < 200 or int(response.status_code) >= 300:
        raise MCPToolError(-32603, await build_image_provider_http_error(response))


def _is_provider_timeout_error(exception: MCPToolError) -> bool:
    return "timed out" in exception.message.lower()


def _require_prompt_id(payload: JSONDict) -> str:
    prompt_id = payload.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise MCPToolError(-32603, "Image generation provider did not return a prompt id.")
    return prompt_id.strip()


def _build_headers(settings: ComfyUIImageSettings) -> dict[str, str]:
    if settings.api_key is None:
        return {}
    return {"Authorization": f"Bearer {settings.api_key}"}


async def _sleep(seconds: float, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return
    await asyncio.sleep(min(float(seconds), remaining))


def _required_text(payload: JSONDict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32602, f"ComfyUI workflow mapping requires {key}.")
    return value.strip()


def _optional_text(payload: JSONDict, key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
