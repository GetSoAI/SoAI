"""SoAI - Static artwork container framing validation [backend/core/plugins/logo_containers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import struct
import zlib

from core.plugins.logo_contract import MAX_LOGO_DIMENSION, InvalidPluginLogo

__all__ = ("validate_logo_dimensions", "validate_png_container", "validate_webp_container")


def validate_logo_dimensions(width: int, height: int) -> None:
    if not (1 <= width <= MAX_LOGO_DIMENSION and 1 <= height <= MAX_LOGO_DIMENSION):
        raise InvalidPluginLogo("Image dimensions must be between 1 and 512 pixels per side.")


def _transparency_matches_color_type(color_type: int, length: int, palette_entries: int) -> bool:
    if color_type == 0:
        return length == 2
    if color_type == 2:
        return length == 6
    if color_type == 3:
        return 1 <= length <= palette_entries
    return color_type not in (4, 6)


def validate_png_container(content: bytes) -> None:
    offset = 8
    chunk_names: set[bytes] = set()
    image_data_ended = False
    color_type = -1
    bit_depth = 0
    palette_entries = 0
    while offset < len(content):
        if len(content) - offset < 12:
            raise InvalidPluginLogo("PNG chunk header is truncated.")
        length = int.from_bytes(content[offset : offset + 4], "big")
        name = content[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(content):
            raise InvalidPluginLogo("PNG chunk payload is truncated.")
        payload = content[offset + 8 : end - 4]
        checksum = int.from_bytes(content[end - 4 : end], "big")
        if zlib.crc32(name + payload) != checksum:
            raise InvalidPluginLogo("PNG chunk checksum is invalid.")
        if len(name) != 4 or not all(65 <= value <= 90 or 97 <= value <= 122 for value in name):
            raise InvalidPluginLogo("PNG chunk type is invalid.")
        if name[2] & 32:
            raise InvalidPluginLogo("PNG chunk reserved bit is invalid.")
        if name in (b"acTL", b"fcTL", b"fdAT"):
            raise InvalidPluginLogo("Animated PNG containers are unsupported.")
        if not chunk_names and name != b"IHDR":
            raise InvalidPluginLogo("PNG must begin with IHDR.")
        if name == b"IHDR":
            if chunk_names or length != 13:
                raise InvalidPluginLogo("PNG image header is invalid.")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            validate_logo_dimensions(width, height)
            color_type = color
            bit_depth = depth
            allowed_depths = {
                0: (1, 2, 4, 8, 16),
                2: (8, 16),
                3: (1, 2, 4, 8),
                4: (8, 16),
                6: (8, 16),
            }
            if (
                depth not in allowed_depths.get(color, ())
                or compression
                or filtering
                or interlace not in (0, 1)
            ):
                raise InvalidPluginLogo("PNG image header fields are unsupported.")
        elif name == b"PLTE":
            if (
                b"PLTE" in chunk_names
                or b"IDAT" in chunk_names
                or not length
                or length > 768
                or length % 3
            ):
                raise InvalidPluginLogo("PNG palette structure is invalid.")
            palette_entries = length // 3
            if color_type in (0, 4) or (color_type == 3 and palette_entries > 2**bit_depth):
                raise InvalidPluginLogo("PNG palette is incompatible with the image header.")
        elif name == b"tRNS":
            if b"tRNS" in chunk_names or b"IDAT" in chunk_names:
                raise InvalidPluginLogo("PNG transparency structure is invalid.")
            if not _transparency_matches_color_type(color_type, length, palette_entries):
                raise InvalidPluginLogo("PNG transparency does not match its color type.")
        elif name == b"IDAT":
            if color_type == 3 and not palette_entries:
                raise InvalidPluginLogo("PNG indexed image is missing its palette.")
            if image_data_ended:
                raise InvalidPluginLogo("PNG image data chunks must be consecutive.")
        elif name == b"IEND":
            if length or b"IDAT" not in chunk_names or end != len(content):
                raise InvalidPluginLogo("PNG termination is invalid or has trailing bytes.")
            return
        if name not in (b"IHDR", b"PLTE", b"IDAT", b"IEND") and not name[0] & 32:
            raise InvalidPluginLogo("PNG contains an unsupported critical chunk.")
        if name != b"IDAT" and b"IDAT" in chunk_names:
            image_data_ended = True
        chunk_names.add(name)
        offset = end
    raise InvalidPluginLogo("PNG termination is missing.")


def validate_webp_container(content: bytes) -> None:
    if len(content) < 20 or int.from_bytes(content[4:8], "little") + 8 != len(content):
        raise InvalidPluginLogo("WebP container length is invalid.")
    offset = 12
    chunk_names: set[bytes] = set()
    canvas_dimensions: tuple[int, int] | None = None
    frame_dimensions: tuple[int, int] | None = None
    while offset < len(content):
        if len(content) - offset < 8:
            raise InvalidPluginLogo("WebP chunk header is truncated.")
        name = content[offset : offset + 4]
        length = int.from_bytes(content[offset + 4 : offset + 8], "little")
        end = offset + 8 + length
        padded_end = end + length % 2
        if padded_end > len(content):
            raise InvalidPluginLogo("WebP chunk payload is truncated.")
        if length % 2 and content[end] != 0:
            raise InvalidPluginLogo("WebP chunk padding is invalid.")
        payload = content[offset + 8 : end]
        if name in (b"ANIM", b"ANMF"):
            raise InvalidPluginLogo("Animated WebP containers are unsupported.")
        if name == b"VP8X":
            if chunk_names or length != 10 or payload[0] & 0xC1 or payload[1:4] != b"\x00\x00\x00":
                raise InvalidPluginLogo("WebP extended header is invalid.")
            if payload[0] & 2:
                raise InvalidPluginLogo("Animated WebP containers are unsupported.")
            canvas_dimensions = (
                int.from_bytes(payload[4:7], "little") + 1,
                int.from_bytes(payload[7:10], "little") + 1,
            )
            validate_logo_dimensions(*canvas_dimensions)
        elif name in (b"VP8 ", b"VP8L"):
            if b"VP8 " in chunk_names or b"VP8L" in chunk_names:
                raise InvalidPluginLogo("WebP must contain exactly one image bitstream.")
            if name == b"VP8L":
                if length < 5 or payload[0] != 0x2F or payload[4] & 0xE0:
                    raise InvalidPluginLogo("WebP lossless header is invalid.")
                packed = int.from_bytes(payload[1:5], "little")
                frame_dimensions = ((packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1)
            else:
                if length < 10 or payload[0] & 1 or payload[3:6] != b"\x9d\x01\x2a":
                    raise InvalidPluginLogo("WebP lossy header is invalid.")
                frame_dimensions = (
                    int.from_bytes(payload[6:8], "little") & 0x3FFF,
                    int.from_bytes(payload[8:10], "little") & 0x3FFF,
                )
            validate_logo_dimensions(*frame_dimensions)
            if canvas_dimensions is not None and canvas_dimensions != frame_dimensions:
                raise InvalidPluginLogo("WebP canvas and image dimensions disagree.")
        chunk_names.add(name)
        offset = padded_end
    if b"VP8 " not in chunk_names and b"VP8L" not in chunk_names:
        raise InvalidPluginLogo("WebP image bitstream is missing.")
