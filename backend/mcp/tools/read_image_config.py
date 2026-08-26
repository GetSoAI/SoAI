"""SoAI - MCP read_image tool limit resolution [backend/mcp/tools/read_image_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.integer_requirements import (
    require_config_int_at_least,
    require_config_int_between,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError

__all__ = ("ReadImageConfig", "resolve_read_image_config")

DEFAULT_READ_IMAGE_MAX_SOURCE_BYTES = 134_217_728
DEFAULT_READ_IMAGE_MAX_ENCODED_CHARS = 16_777_216
DEFAULT_READ_IMAGE_MAX_PIXELS = 4_000_000
DEFAULT_READ_IMAGE_JPEG_QUALITY = 85


@dataclass(frozen=True, slots=True)
class ReadImageConfig:
    max_source_bytes: int
    max_encoded_chars: int
    max_pixels: int
    jpeg_quality: int


def resolve_read_image_config(config: ConfigProtocol) -> ReadImageConfig:
    try:
        return ReadImageConfig(
            max_source_bytes=require_config_int_at_least(
                config.get(
                    "TOOLS.MCP.READ_IMAGE.MAX_SOURCE_BYTES",
                    DEFAULT_READ_IMAGE_MAX_SOURCE_BYTES,
                ),
                key="TOOLS.MCP.READ_IMAGE.MAX_SOURCE_BYTES",
                minimum=1,
            ),
            max_encoded_chars=require_config_int_at_least(
                config.get(
                    "TOOLS.MCP.READ_IMAGE.MAX_ENCODED_CHARS",
                    DEFAULT_READ_IMAGE_MAX_ENCODED_CHARS,
                ),
                key="TOOLS.MCP.READ_IMAGE.MAX_ENCODED_CHARS",
                minimum=4,
            ),
            max_pixels=require_config_int_at_least(
                config.get("TOOLS.MCP.READ_IMAGE.MAX_PIXELS", DEFAULT_READ_IMAGE_MAX_PIXELS),
                key="TOOLS.MCP.READ_IMAGE.MAX_PIXELS",
                minimum=1,
            ),
            jpeg_quality=require_config_int_between(
                config.get("TOOLS.MCP.READ_IMAGE.JPEG_QUALITY", DEFAULT_READ_IMAGE_JPEG_QUALITY),
                key="TOOLS.MCP.READ_IMAGE.JPEG_QUALITY",
                minimum=40,
                maximum=95,
            ),
        )
    except AttributeError as exception:
        raise ConfigurationError(
            "read_image config requires a ConfigProtocol provider.",
        ) from exception
