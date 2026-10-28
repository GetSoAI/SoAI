"""SoAI - Bounded non-destructive image decoding [backend/core/files/image_inspection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from PIL import Image

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.validation.strict_numbers import require_positive_int_strict

__all__ = ("InspectedImage", "open_inspected_image")


@dataclass(frozen=True, slots=True)
class InspectedImage:
    image: Image.Image
    content_type: str | None
    width: int
    height: int
    orientation: int
    has_alpha: bool
    animated: bool


def _validate_dimensions(image: Image.Image, maximum_pixels: int) -> None:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValidationError("The image has invalid dimensions.")
    if width * height > maximum_pixels:
        raise PayloadTooLargeError("The image exceeds the permitted decoded pixel limit.")


@contextmanager
def open_inspected_image(
    image_bytes: bytes,
    *,
    maximum_bytes: int,
    maximum_pixels: int,
    animation: Literal["reject", "first_frame"],
    allowed_content_types: frozenset[str] | None = None,
    orientation_policy: Literal["strict", "permissive"] = "strict",
) -> Generator[InspectedImage]:
    require_positive_int_strict(maximum_bytes, error_message="Image byte limit must be positive.")
    require_positive_int_strict(maximum_pixels, error_message="Image pixel limit must be positive.")
    if animation not in {"reject", "first_frame"}:
        raise ValidationError("Image animation policy is invalid.")
    if orientation_policy not in {"strict", "permissive"}:
        raise ValidationError("Image orientation policy is invalid.")
    if len(image_bytes) > maximum_bytes:
        raise PayloadTooLargeError("The image exceeds the permitted encoded byte limit.")
    with Image.open(io.BytesIO(image_bytes)) as header:
        _validate_dimensions(header, maximum_pixels)
        content_type = Image.MIME.get(header.format or "")
        if allowed_content_types is not None and (
            content_type is None or content_type not in allowed_content_types
        ):
            raise ValidationError("This image format is not supported for this operation.")
        header.verify()
    with Image.open(io.BytesIO(image_bytes)) as decoded:
        _validate_dimensions(decoded, maximum_pixels)
        try:
            decoded.seek(1)
        except EOFError:
            animated = False
        else:
            animated = True
        if animated and animation == "reject":
            raise ValidationError("Animated images are not supported for this operation.")
        decoded.seek(0)
        _validate_dimensions(decoded, maximum_pixels)
        decoded.load()
        orientation_value = decoded.getexif().get(274, 1)
        if not isinstance(orientation_value, int) or orientation_value not in range(1, 9):
            if orientation_policy == "strict":
                raise ValidationError("The image has invalid orientation metadata.")
            orientation_value = 1
        width, height = decoded.size
        if orientation_value in {5, 6, 7, 8}:
            width, height = height, width
        yield InspectedImage(
            image=decoded,
            content_type=content_type,
            width=width,
            height=height,
            orientation=orientation_value,
            has_alpha="A" in decoded.getbands() or "transparency" in decoded.info,
            animated=animated,
        )
