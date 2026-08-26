"""SoAI - MCP utility tool definition: generate_image [backend/mcp/tools/utility_tool_definitions/generate_image.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_IMAGE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_generate_image_tool_definitions",)

_MAX_SEED_VALUE = 2_147_483_647
_MAX_DIMENSION = 2048
_DIMENSION_MULTIPLE = 8


def build_generate_image_tool_definitions() -> dict[str, JSONDict]:
    return {
        "generate_image": {
            "title": "Generate Image",
            "description": (
                "Generate an image from a clear English prompt using SoAI's configured image "
                "engine. Before calling this tool, translate or rewrite the user's visual request "
                "into English; non-English prompts can produce poor output. SoAI supports local "
                "Automatic1111, local ComfyUI with a configured API workflow, and explicit AI "
                "Horde. Local Automatic1111 is the default engine. AI Horde is a public queue and "
                "may take a long time; SoAI waits while the provider reports the request remains "
                "possible and stops when the provider rejects, faults, or exceeds the configured "
                "generation ceiling. Width and height must each be from 64 to 2048 pixels and "
                "multiples of 8. For wallpaper, wide, landscape, or 16:9 requests, explicitly pass "
                "a wide size such as width 1344 and height 768 when the configured engine can "
                "support it. This creates provider or local generator work outside the model and "
                "requires approval."
            ),
            "icons": [build_tool_icon_entry(ICON_IMAGE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["prompt"],
                "properties": {
                    "prompt": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                        "description": "English image prompt, from 1 to 2000 characters.",
                    },
                    "negative_prompt": {
                        "type": "string",
                        "maxLength": 2000,
                        "description": "Optional English negative prompt.",
                    },
                    "width": {
                        "type": "integer",
                        "minimum": 64,
                        "maximum": _MAX_DIMENSION,
                        "multipleOf": _DIMENSION_MULTIPLE,
                        "description": "Generated image width in pixels. Defaults to configuration.",
                    },
                    "height": {
                        "type": "integer",
                        "minimum": 64,
                        "maximum": _MAX_DIMENSION,
                        "multipleOf": _DIMENSION_MULTIPLE,
                        "description": "Generated image height in pixels. Defaults to configuration.",
                    },
                    "steps": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 150,
                        "description": "Optional generation step count.",
                    },
                    "cfg_scale": {
                        "type": "number",
                        "minimum": 1.0,
                        "maximum": 30.0,
                        "description": "Optional classifier-free guidance scale.",
                    },
                    "seed": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": _MAX_SEED_VALUE,
                        "description": "Optional deterministic generation seed.",
                    },
                },
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "provider",
                    "content_type",
                    "image_base64",
                    "size_bytes",
                    "width",
                    "height",
                    "elapsed_ms",
                ],
                "properties": {
                    "provider": {"type": "string"},
                    "content_type": {
                        "type": "string",
                        "enum": ["image/jpeg", "image/png", "image/webp"],
                    },
                    "image_base64": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "seed": {"type": "integer"},
                    "elapsed_ms": {"type": "integer"},
                },
            },
            "annotations": {
                **build_tool_annotation_flags(open_world=True),
                "requiresApprovalHint": True,
            },
        },
    }
