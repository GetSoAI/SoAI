"""SoAI - WebUI attachment provider image shaping [backend/features/api/runtime/webui_attachments/provider_image_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.files.descriptor_reading import read_descriptor_at
from core.files.inline_image_preparation import prepare_inline_image_for_prompt_relay
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("ProviderImageProjection", "shape_descriptor_image_for_provider")

_MAX_SOURCE_BYTES_KEY = "SERVER.WEBUI.PROVIDER_IMAGE.MAX_SOURCE_BYTES"
_MAX_PIXELS_KEY = "SERVER.WEBUI.PROVIDER_IMAGE.MAX_PIXELS"
_JPEG_QUALITY_KEY = "SERVER.WEBUI.PROVIDER_IMAGE.JPEG_QUALITY"
_READ_CHUNK_BYTES = MIB_BYTES
_EXCESS_BYTE_COUNT = 1


@dataclass(frozen=True, slots=True)
class ProviderImageProjection:
    part: JSONDict | None
    failure_reason: str | None


def _read_descriptor_limited(descriptor: int, *, max_bytes: int) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    offset = 0
    while total <= max_bytes:
        chunk = read_descriptor_at(
            descriptor,
            min(_READ_CHUNK_BYTES, max_bytes + _EXCESS_BYTE_COUNT - total),
            offset,
        )
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        offset += len(chunk)
        if total > max_bytes:
            return None
    return None


def _image_part_from_payload(payload: JSONDict) -> JSONDict | None:
    content_type = payload.get("content_type")
    image_base64 = payload.get("image_base64")
    if not isinstance(content_type, str) or not content_type:
        return None
    if not isinstance(image_base64, str) or not image_base64:
        return None
    data_url = f"data:{content_type};base64,{image_base64}"
    return {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}


def shape_descriptor_image_for_provider(
    *,
    descriptor: int,
    declared_content_type: str | None,
    config: ConfigProtocol,
    max_encoded_chars: int,
) -> ProviderImageProjection:
    max_source_bytes = max(1, config.get_int(_MAX_SOURCE_BYTES_KEY))
    try:
        image_bytes = _read_descriptor_limited(descriptor, max_bytes=max_source_bytes)
    except OSError:
        return ProviderImageProjection(part=None, failure_reason="Image source could not be read.")
    if image_bytes is None:
        return ProviderImageProjection(
            part=None,
            failure_reason="Image source exceeded the size limit.",
        )
    prepared, failure_reason = prepare_inline_image_for_prompt_relay(
        image_bytes=image_bytes,
        declared_content_type=declared_content_type,
        max_source_bytes=max_source_bytes,
        max_encoded_chars=max_encoded_chars,
        max_pixels=config.get_int(_MAX_PIXELS_KEY),
        jpeg_quality=config.get_int(_JPEG_QUALITY_KEY),
    )
    if prepared is None:
        return ProviderImageProjection(part=None, failure_reason=failure_reason)
    image_part = _image_part_from_payload(prepared.payload)
    if image_part is None:
        return ProviderImageProjection(part=None, failure_reason="Image payload encoding failed.")
    return ProviderImageProjection(part=image_part, failure_reason=None)
