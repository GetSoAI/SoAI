"""SoAI - MCP generate image configuration resolution [backend/mcp/tools/generate_image_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes
from core.config.numeric_lenient import (
    coerce_lenient_bounded_float,
    coerce_lenient_clamped_int,
    coerce_lenient_positive_int,
)
from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict, parse_json_str_list
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from mcp.tools.configured_http_endpoint import resolve_configured_endpoint_base_url
from mcp.tools.error import MCPToolError
from mcp.tools.generate_image_horde_constants import (
    ANONYMOUS_HORDE_API_KEY,
    DEFAULT_HORDE_BASE_URL,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = (
    "Automatic1111ImageSettings",
    "ComfyUIImageSettings",
    "GenerateImageSettings",
    "HordeImageSettings",
    "resolve_generate_image_settings",
)

_PREFIX = "TOOLS.MCP.GENERATE_IMAGE"
_ENGINES = frozenset({"automatic1111", "comfyui", "ai_horde"})


@dataclass(frozen=True, slots=True)
class Automatic1111ImageSettings:
    base_url: str
    basic_auth: str | None
    sampler_name: str | None
    scheduler: str | None
    extra_params: JSONDict


@dataclass(frozen=True, slots=True)
class ComfyUIImageSettings:
    base_url: str
    api_key: str | None
    model: str | None
    workflow: JSONDict
    workflow_nodes: tuple[JSONDict, ...]
    output_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HordeImageSettings:
    base_url: str
    api_key: str
    model: str
    max_generation_wait_sec: float


@dataclass(frozen=True, slots=True)
class GenerateImageSettings:
    engine: str
    default_width: int
    default_height: int
    default_steps: int
    default_cfg_scale: float
    negative_prompt: str
    timeout_sec: float
    poll_interval_sec: float
    max_image_bytes: int
    automatic1111: Automatic1111ImageSettings
    comfyui: ComfyUIImageSettings
    ai_horde: HordeImageSettings


def resolve_generate_image_settings(config: ConfigProtocol) -> GenerateImageSettings:
    engine = _read_string(config, "ENGINE", "automatic1111").lower()
    if engine not in _ENGINES:
        raise MCPToolError(-32602, "TOOLS.MCP.GENERATE_IMAGE.ENGINE is invalid.")
    return GenerateImageSettings(
        engine=engine,
        default_width=_read_dimension(config, "DEFAULT_WIDTH", 704),
        default_height=_read_dimension(config, "DEFAULT_HEIGHT", 704),
        default_steps=coerce_lenient_clamped_int(
            config.get(f"{_PREFIX}.DEFAULT_STEPS"),
            default=20,
            minimum=1,
            maximum=150,
        ),
        default_cfg_scale=coerce_lenient_bounded_float(
            config.get(f"{_PREFIX}.DEFAULT_CFG_SCALE"),
            default=7.0,
            minimum=1.0,
            maximum=30.0,
        ),
        negative_prompt=_read_string(config, "NEGATIVE_PROMPT", ""),
        timeout_sec=coerce_lenient_bounded_float(
            config.get(f"{_PREFIX}.TIMEOUT_SEC"),
            default=3600.0,
            minimum=1.0,
            maximum=21600.0,
        ),
        poll_interval_sec=coerce_lenient_bounded_float(
            config.get(f"{_PREFIX}.POLL_INTERVAL_SEC"),
            default=1.0,
            minimum=0.25,
            maximum=30.0,
        ),
        max_image_bytes=coerce_lenient_positive_int(
            config.get(f"{_PREFIX}.MAX_IMAGE_BYTES"),
            default=mib_to_bytes(128),
            minimum=1,
            maximum=mib_to_bytes(128),
        ),
        automatic1111=_resolve_automatic1111_settings(config),
        comfyui=_resolve_comfyui_settings(config),
        ai_horde=_resolve_horde_settings(config),
    )


def _resolve_automatic1111_settings(config: ConfigProtocol) -> Automatic1111ImageSettings:
    return Automatic1111ImageSettings(
        base_url=_read_base_url(config, "AUTOMATIC1111.BASE_URL", "http://127.0.0.1:7860"),
        basic_auth=_read_optional_string(config, "AUTOMATIC1111.BASIC_AUTH"),
        sampler_name=_read_optional_string(config, "AUTOMATIC1111.SAMPLER_NAME"),
        scheduler=_read_optional_string(config, "AUTOMATIC1111.SCHEDULER"),
        extra_params=_read_json_object(config, "AUTOMATIC1111.EXTRA_PARAMS_JSON"),
    )


def _resolve_comfyui_settings(config: ConfigProtocol) -> ComfyUIImageSettings:
    return ComfyUIImageSettings(
        base_url=_read_base_url(config, "COMFYUI.BASE_URL", "http://127.0.0.1:8188"),
        api_key=_read_optional_string(config, "COMFYUI.API_KEY"),
        model=_read_optional_string(config, "COMFYUI.MODEL"),
        workflow=_read_json_object(config, "COMFYUI.WORKFLOW_JSON"),
        workflow_nodes=tuple(_read_mapping_list(config, "COMFYUI.WORKFLOW_NODES")),
        output_node_ids=tuple(_read_string_list(config, "COMFYUI.OUTPUT_NODE_IDS")),
    )


def _resolve_horde_settings(config: ConfigProtocol) -> HordeImageSettings:
    return HordeImageSettings(
        base_url=_read_base_url(config, "AI_HORDE.BASE_URL", DEFAULT_HORDE_BASE_URL),
        api_key=_read_string(config, "AI_HORDE.API_KEY", ANONYMOUS_HORDE_API_KEY),
        model=_read_string(config, "AI_HORDE.MODEL", "stable_diffusion"),
        max_generation_wait_sec=coerce_lenient_bounded_float(
            config.get(f"{_PREFIX}.AI_HORDE.MAX_GENERATION_WAIT_SEC"),
            default=3600.0,
            minimum=60.0,
            maximum=21600.0,
        ),
    )


def _read_base_url(config: ConfigProtocol, suffix: str, default: str) -> str:
    return resolve_configured_endpoint_base_url(
        raw_base_url=_read_string(config, suffix, default),
        default_base_url=default,
        config_key=f"{_PREFIX}.{suffix}",
    )


def _read_dimension(config: ConfigProtocol, suffix: str, default: int) -> int:
    value = coerce_lenient_clamped_int(
        config.get(f"{_PREFIX}.{suffix}"),
        default=default,
        minimum=64,
        maximum=2048,
    )
    if value % 8 != 0:
        raise MCPToolError(-32602, f"{_PREFIX}.{suffix} must be a multiple of 8.")
    return value


def _read_string(config: ConfigProtocol, suffix: str, default: str) -> str:
    raw_value = config.get(f"{_PREFIX}.{suffix}")
    if isinstance(raw_value, str):
        return raw_value.strip() or default
    return default


def _read_optional_string(config: ConfigProtocol, suffix: str) -> str | None:
    raw_value = config.get(f"{_PREFIX}.{suffix}")
    if not isinstance(raw_value, str):
        return None
    return coerce_optional_trimmed_str(raw_value)


def _read_json_object(config: ConfigProtocol, suffix: str) -> JSONDict:
    value = _read_string(config, suffix, "")
    if not value:
        return {}
    try:
        return parse_json_dict(value, field=f"{_PREFIX}.{suffix}")
    except ValidationError as exception:
        raise MCPToolError(
            -32602,
            f"{_PREFIX}.{suffix} must be a JSON object string.",
        ) from exception


def _read_string_list(config: ConfigProtocol, suffix: str) -> list[str]:
    raw_value = config.get(f"{_PREFIX}.{suffix}")
    if isinstance(raw_value, list | tuple):
        values: list[str] = []
        for item in raw_value:
            if not isinstance(item, str):
                raise MCPToolError(-32602, f"{_PREFIX}.{suffix} must contain only strings.")
            normalized = item.strip()
            if normalized:
                values.append(normalized)
        return values
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            return parse_json_str_list(
                raw_value,
                field=f"{_PREFIX}.{suffix}",
                strip_items=True,
                drop_empty=True,
            )
        except ValidationError as exception:
            raise MCPToolError(
                -32602,
                f"{_PREFIX}.{suffix} must be a JSON string list.",
            ) from exception
    return []


def _read_mapping_list(config: ConfigProtocol, suffix: str) -> list[JSONDict]:
    raw_value = config.get(f"{_PREFIX}.{suffix}")
    if not isinstance(raw_value, list | tuple):
        return []
    mappings: list[JSONDict] = []
    for item in raw_value:
        if not is_json_dict(item):
            raise MCPToolError(-32602, f"{_PREFIX}.{suffix} must contain only mappings.")
        mappings.append(item)
    return mappings
