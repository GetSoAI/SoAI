"""SoAI - Optional plugin artwork decoding and sanitization [backend/core/plugins/logo_images.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import zlib

from PIL import Image, UnidentifiedImageError

from core.files.image_signature import validate_image_signature
from core.plugins.logo_containers import (
    validate_logo_dimensions,
    validate_png_container,
    validate_webp_container,
)
from core.plugins.logo_contract import (
    LOGO_FILENAMES,
    MAX_LOGO_OUTPUT_BYTES,
    MAX_LOGO_SOURCE_BYTES,
    InvalidPluginLogo,
    PluginLogoResult,
    PluginLogoSource,
)

__all__ = ("sanitize_plugin_logo",)


def _rgba_pixels(source: Image.Image, *, png_bit_depth: int | None = None) -> Image.Image:
    raw_transparency: int | float | tuple[int, ...] | bytes | None = source.info.get("transparency")
    if (
        source.mode == "RGB"
        and isinstance(raw_transparency, tuple)
        and len(raw_transparency) == 3
        and all(isinstance(value, int) for value in raw_transparency)
    ):
        transparent_rgb = tuple(
            max(0, min(255, value >> 8 if png_bit_depth == 16 else value))
            for value in raw_transparency
        )
        converted = source.convert("RGBA")
        rgba_pixels: list[tuple[int, int, int, int]] = []
        for row in range(converted.height):
            for column in range(converted.width):
                pixel = converted.getpixel((column, row))
                if (
                    not isinstance(pixel, tuple)
                    or len(pixel) != 4
                    or not all(isinstance(value, int) for value in pixel)
                ):
                    raise InvalidPluginLogo("PNG RGB sample is invalid.")
                red, green, blue, alpha = pixel
                rgb = (red, green, blue)
                rgba_pixels.append((*rgb, 0 if rgb == transparent_rgb else alpha))
        converted.putdata(rgba_pixels)
        return converted
    if source.mode not in ("I", "I;16", "I;16B", "I;16L"):
        return source.convert("RGBA")
    grayscale_transparency = raw_transparency if isinstance(raw_transparency, int) else None
    grayscale_pixels: list[tuple[int, int, int, int]] = []
    for row in range(source.height):
        for column in range(source.width):
            raw_value: int | float | tuple[int, ...] | None = source.getpixel((column, row))
            if not isinstance(raw_value, int):
                raise InvalidPluginLogo("PNG grayscale sample is invalid.")
            intensity = max(0, min(255, raw_value // 256))
            grayscale_pixels.append(
                (
                    intensity,
                    intensity,
                    intensity,
                    0 if raw_value == grayscale_transparency else 255,
                )
            )
    converted = Image.new("RGBA", source.size)
    converted.putdata(grayscale_pixels)
    return converted


def sanitize_plugin_logo(source: PluginLogoSource) -> PluginLogoResult:
    if source.rejection is not None:
        return PluginLogoResult(status="invalid", reason=source.rejection)
    if source.filename is None:
        return PluginLogoResult(status="absent")
    try:
        if source.filename not in LOGO_FILENAMES:
            raise InvalidPluginLogo("Artwork must be a regular root logo.png or logo.webp.")
        if not 1 <= len(source.content) <= MAX_LOGO_SOURCE_BYTES:
            raise InvalidPluginLogo("Artwork source must contain between 1 and 1048576 bytes.")
        valid_signature, mime_type = validate_image_signature(source.content[:16])
        expected_format = "PNG" if source.filename == "logo.png" else "WEBP"
        expected_mime = "image/png" if expected_format == "PNG" else "image/webp"
        if not valid_signature or mime_type != expected_mime:
            raise InvalidPluginLogo("Artwork filename and image signature disagree.")
        if expected_format == "PNG":
            validate_png_container(source.content)
        else:
            validate_webp_container(source.content)
        with Image.open(io.BytesIO(source.content)) as decoded:
            if decoded.format != expected_format:
                raise InvalidPluginLogo("Artwork container and decoded format disagree.")
            validate_logo_dimensions(*decoded.size)
            decoded.load()
            with (
                _rgba_pixels(
                    decoded,
                    png_bit_depth=(source.content[24] if expected_format == "PNG" else None),
                ) as converted,
                Image.frombytes("RGBA", converted.size, converted.tobytes()) as clean,
            ):
                output = io.BytesIO()
                clean.save(output, format="PNG")
                content = output.getvalue()
                width, height = clean.size
        if len(content) > MAX_LOGO_OUTPUT_BYTES:
            raise InvalidPluginLogo("Prepared artwork exceeds 2097152 bytes.")
        return PluginLogoResult(status="available", content=content, width=width, height=height)
    except InvalidPluginLogo as exception:
        return PluginLogoResult(status="invalid", reason=str(exception))
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, zlib.error):
        return PluginLogoResult(
            status="invalid", reason="Artwork pixel decoding or encoding failed."
        )
