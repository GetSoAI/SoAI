"""SoAI - MCP utility tool handler: generate_image [backend/mcp/tools/generate_image.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx2

from core.files.image_signature import validate_image_signature
from core.files.inline_image_payload import (
    MAX_INLINE_IMAGE_BASE64_CHARS,
    build_inline_image_payload,
)
from mcp.tools.argument_fields import (
    optional_bounded_string,
    require_allowed_keys,
    require_bounded_string,
)
from mcp.tools.argument_scalars import (
    parse_optional_int_strict,
    parse_optional_number_strict,
)
from mcp.tools.configured_http_endpoint import (
    ConfiguredEndpointNetworkTarget,
    resolve_configured_endpoint_network_target,
)
from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_automatic1111 import generate_with_automatic1111
from mcp.tools.generate_image_comfyui import generate_with_comfyui
from mcp.tools.generate_image_config import (
    GenerateImageSettings,
    resolve_generate_image_settings,
)
from mcp.tools.generate_image_horde import generate_with_horde
from mcp.tools.generate_image_types import (
    ImageGenerationDeadline,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from mcp.tools.provider_http import map_provider_http_exception

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_generate_image",)

_MIN_DIMENSION = 64
_MAX_DIMENSION = 2048
_DIMENSION_MULTIPLE = 8
_MAX_SEED = 2_147_483_647
_SUPPORTED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_ALLOWED_ARGUMENT_KEYS = frozenset(
    {"prompt", "negative_prompt", "width", "height", "seed", "steps", "cfg_scale"},
)


def _require_execute_mode(utility_tools: MCPUtilityToolsProtocol) -> None:
    request_context = utility_tools.active_request_context.get()
    if request_context is None:
        return
    agent_mode = request_context.agent_mode
    if isinstance(agent_mode, str) and agent_mode.strip().lower() == "plan":
        raise MCPToolError(
            -32602,
            "generate_image is not available in plan mode. Switch to execute mode to create images.",
        )


def _parse_dimension(arguments: JSONDict, field_name: str, default: int) -> int:
    parsed = parse_optional_int_strict(
        arguments.get(field_name),
        field_name=field_name,
        min_value=_MIN_DIMENSION,
        max_value=_MAX_DIMENSION,
    )
    value = default if parsed is None else int(parsed)
    if value % _DIMENSION_MULTIPLE != 0:
        raise MCPToolError(
            -32602,
            f"{field_name} must be a multiple of {_DIMENSION_MULTIPLE}.",
        )
    return value


def _build_request(arguments: JSONDict, settings: GenerateImageSettings) -> ImageGenerationRequest:
    prompt = require_bounded_string(arguments.get("prompt"), field="prompt", max_length=2000)
    negative_prompt = optional_bounded_string(
        arguments.get("negative_prompt"),
        field="negative_prompt",
        max_length=2000,
    )
    seed = parse_optional_int_strict(
        arguments.get("seed"),
        field_name="seed",
        min_value=0,
        max_value=_MAX_SEED,
    )
    steps = parse_optional_int_strict(
        arguments.get("steps"),
        field_name="steps",
        min_value=1,
        max_value=150,
    )
    cfg_scale = parse_optional_number_strict(
        arguments.get("cfg_scale"),
        field_name="cfg_scale",
        min_value=1.0,
        max_value=30.0,
    )
    return ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=(
            negative_prompt if negative_prompt is not None else settings.negative_prompt
        ),
        width=_parse_dimension(arguments, "width", settings.default_width),
        height=_parse_dimension(arguments, "height", settings.default_height),
        steps=settings.default_steps if steps is None else int(steps),
        cfg_scale=settings.default_cfg_scale if cfg_scale is None else float(cfg_scale),
        seed=seed,
    )


def _validate_image_body(image_bytes: bytes) -> str:
    is_valid, content_type = validate_image_signature(image_bytes[:32])
    if not is_valid or content_type is None:
        raise MCPToolError(-32603, "Image generation provider returned a non-image response.")
    if content_type not in _SUPPORTED_IMAGE_TYPES:
        raise MCPToolError(
            -32603,
            f"Image generation provider returned unsupported content type: {content_type}.",
        )
    return content_type


async def _resolve_network_target(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    engine: str,
    base_url: str,
) -> ConfiguredEndpointNetworkTarget:
    return await resolve_configured_endpoint_network_target(
        config=utility_tools.config,
        runtime_flags=utility_tools.runtime_flags,
        endpoint_base_url=base_url,
        config_key=f"TOOLS.MCP.GENERATE_IMAGE.{engine.upper()}.BASE_URL",
        tool_name="generate_image",
        capability="image generation provider access",
        config_prefix="TOOLS.MCP.GENERATE_IMAGE",
        local_policy_source=f"MCP generate_image {engine} provider",
        network_blocked_message="Image generation provider network policy blocked access.",
    )


async def _generate(
    utility_tools: MCPUtilityToolsProtocol,
    settings: GenerateImageSettings,
    request: ImageGenerationRequest,
    deadline: ImageGenerationDeadline,
) -> ImageGenerationResult:
    http_client = utility_tools.http_client
    if http_client is None:
        raise MCPToolError(-32603, "HTTP client is not available")
    if settings.engine == "automatic1111":
        target = await _resolve_network_target(
            utility_tools,
            engine="automatic1111",
            base_url=settings.automatic1111.base_url,
        )
        return await generate_with_automatic1111(
            http_client=http_client,
            base_url=target.base_url,
            settings=settings.automatic1111,
            request=request,
            deadline=deadline,
            extensions=target.extensions,
        )
    if settings.engine == "comfyui":
        target = await _resolve_network_target(
            utility_tools,
            engine="comfyui",
            base_url=settings.comfyui.base_url,
        )
        return await generate_with_comfyui(
            http_client=http_client,
            base_url=target.base_url,
            settings=settings.comfyui,
            request=request,
            deadline=deadline,
            poll_interval_sec=settings.poll_interval_sec,
            extensions=target.extensions,
        )
    target = await _resolve_network_target(
        utility_tools,
        engine="ai_horde",
        base_url=settings.ai_horde.base_url,
    )
    return await generate_with_horde(
        utility_tools=utility_tools,
        base_url=target.base_url,
        api_key=settings.ai_horde.api_key,
        model=settings.ai_horde.model,
        request=request,
        deadline=deadline,
        poll_interval_sec=settings.poll_interval_sec,
        extensions=target.extensions,
    )


async def tool_generate_image(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(arguments, allowed_keys=_ALLOWED_ARGUMENT_KEYS, tool_name="generate_image")
    if not bool(utility_tools.config.get_bool("TOOLS.MCP.GENERATE_IMAGE.ENABLED")):
        raise MCPToolError(
            -32603,
            "generate_image is disabled by configuration (TOOLS.MCP.GENERATE_IMAGE.ENABLED=false).",
        )
    _require_execute_mode(utility_tools)
    settings = resolve_generate_image_settings(utility_tools.config)
    request = _build_request(arguments, settings)
    start_monotonic = time.monotonic()
    deadline = ImageGenerationDeadline(start_monotonic + _effective_timeout_sec(settings))
    try:
        result = await _generate(utility_tools, settings, request, deadline)
    except httpx2.HTTPError as exception:
        raise map_provider_http_exception(
            exception,
            timeout_message="Image generation provider timed out while processing the request.",
            request_failed_message="Image generation provider request failed.",
        ) from exception
    elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
    if len(result.image_bytes) > settings.max_image_bytes:
        raise MCPToolError(-32603, "Image generation provider response exceeded size limit.")
    content_type = _validate_image_body(result.image_bytes)
    inline_payload, failure_reason = build_inline_image_payload(
        content_type=content_type,
        image_bytes=result.image_bytes,
        max_base64_chars=MAX_INLINE_IMAGE_BASE64_CHARS,
    )
    if inline_payload is None:
        raise MCPToolError(
            -32603,
            failure_reason or "Image generation payload exceeded size limit.",
        )
    return {
        "provider": result.provider,
        "content_type": content_type,
        "image_base64": str(inline_payload["image_base64"]),
        "size_bytes": len(result.image_bytes),
        "width": result.width,
        "height": result.height,
        **({"seed": int(result.seed)} if result.seed is not None else {}),
        "elapsed_ms": elapsed_ms,
    }


def _effective_timeout_sec(settings: GenerateImageSettings) -> float:
    if settings.engine == "ai_horde":
        return settings.ai_horde.max_generation_wait_sec
    return settings.timeout_sec
