"""SoAI - Inline image JPEG resizing and encoding [backend/core/files/inline_image_jpeg_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io

from PIL import Image

from core.files.inline_image_payload import estimate_inline_image_base64_chars

__all__ = ("prepare_opened_image_as_jpeg",)


def prepare_opened_image_as_jpeg(
    *,
    image: Image.Image,
    max_pixels: int,
    max_encoded_chars: int,
    jpeg_quality: int,
) -> tuple[bytes, int, int, int, int]:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("invalid_image_dimensions")
    target_width, target_height = _compute_downscaled_dimensions(
        width=width,
        height=height,
        max_pixels=max_pixels,
    )
    rgb_source = _convert_image_to_rgb(image)
    prepared_bytes, prepared_width, prepared_height = _encode_jpeg_under_limit(
        rgb_source=rgb_source,
        target_width=target_width,
        target_height=target_height,
        jpeg_quality=jpeg_quality,
        max_encoded_chars=max_encoded_chars,
    )
    return (prepared_bytes, width, height, prepared_width, prepared_height)


def _encode_jpeg_under_limit(
    *,
    rgb_source: Image.Image,
    target_width: int,
    target_height: int,
    jpeg_quality: int,
    max_encoded_chars: int,
) -> tuple[bytes, int, int]:
    current_width = max(1, int(target_width))
    current_height = max(1, int(target_height))
    quality = _normalize_jpeg_quality(jpeg_quality)
    encoded_limit = max(4, int(max_encoded_chars))
    for _attempt in range(16):
        prepared = _resize_rgb_source(
            rgb_source=rgb_source,
            width=current_width,
            height=current_height,
        )
        prepared_bytes = _encode_jpeg_bytes(prepared, quality=quality)
        estimated_chars = estimate_inline_image_base64_chars(len(prepared_bytes))
        if estimated_chars <= encoded_limit:
            return (prepared_bytes, current_width, current_height)
        if quality > 60:
            quality = max(60, quality - 10)
            continue
        next_width, next_height = _shrink_dimensions_for_encoded_limit(
            width=current_width,
            height=current_height,
            estimated_chars=estimated_chars,
            max_encoded_chars=encoded_limit,
        )
        if next_width == current_width and next_height == current_height:
            break
        current_width, current_height = next_width, next_height
        quality = _normalize_jpeg_quality(jpeg_quality)
    raise ValueError("image_exceeds_encoded_limit")


def _resize_rgb_source(*, rgb_source: Image.Image, width: int, height: int) -> Image.Image:
    if rgb_source.size == (width, height):
        return rgb_source
    return rgb_source.resize((width, height), Image.Resampling.LANCZOS)


def _encode_jpeg_bytes(image: Image.Image, *, quality: int) -> bytes:
    output_buffer = io.BytesIO()
    image.save(
        output_buffer,
        format="JPEG",
        quality=int(quality),
        optimize=True,
    )
    return output_buffer.getvalue()


def _normalize_jpeg_quality(value: int) -> int:
    return max(40, min(95, int(value)))


def _shrink_dimensions_for_encoded_limit(
    *,
    width: int,
    height: int,
    estimated_chars: int,
    max_encoded_chars: int,
) -> tuple[int, int]:
    if estimated_chars <= 0:
        return (width, height)
    scale = (float(max_encoded_chars) / float(estimated_chars)) ** 0.5
    scaled = max(0.1, min(0.85, scale * 0.95))
    next_width = max(1, int(width * scaled))
    next_height = max(1, int(height * scaled))
    if next_width == width and width > 1:
        next_width -= 1
    if next_height == height and height > 1:
        next_height -= 1
    return (next_width, next_height)


def _convert_image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.getchannel("A")
        background.paste(image.convert("RGB"), mask=alpha)
        return background
    if image.mode == "P" and "transparency" in image.info:
        converted = image.convert("RGBA")
        background = Image.new("RGB", converted.size, (255, 255, 255))
        background.paste(converted.convert("RGB"), mask=converted.getchannel("A"))
        return background
    return image.convert("RGB")


def _compute_downscaled_dimensions(
    *,
    width: int,
    height: int,
    max_pixels: int,
) -> tuple[int, int]:
    pixel_limit = max(1, int(max_pixels))
    source_pixels = width * height
    if source_pixels <= pixel_limit:
        return (width, height)
    scale = (pixel_limit / source_pixels) ** 0.5
    target_width = max(1, int(width * scale))
    target_height = max(1, int(height * scale))
    while target_width * target_height > pixel_limit:
        if target_width >= target_height:
            target_width = max(1, target_width - 1)
            continue
        target_height = max(1, target_height - 1)
    return (target_width, target_height)
