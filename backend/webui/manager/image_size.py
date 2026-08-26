"""SoAI - Image size extraction utilities [backend/webui/manager/image_size.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import struct

from core.filesystem.open_files import open_binary

__all__ = ("extract_image_size_sync",)


def extract_image_size_sync(file_path: str, mime_type: str | None) -> tuple[int, int] | None:
    parsers: list[str] = []
    normalized_mime = (mime_type or "").lower()
    if "png" in normalized_mime:
        parsers.append("png")
    if "gif" in normalized_mime:
        parsers.append("gif")
    if "webp" in normalized_mime:
        parsers.append("webp")
    if "jpeg" in normalized_mime or "jpg" in normalized_mime:
        parsers.append("jpeg")
    for default in ("png", "gif", "webp", "jpeg"):
        if default not in parsers:
            parsers.append(default)
    header = b""
    with open_binary(file_path, mode="rb") as file_handle:
        header = file_handle.read(64)
    for parser in parsers:
        if parser == "png":
            size = _read_png_size(header)
        elif parser == "gif":
            size = _read_gif_size(header)
        elif parser == "webp":
            size = _read_webp_size(file_path, header)
        elif parser == "jpeg":
            size = _read_jpeg_size(file_path)
        else:
            continue
        if size:
            return size
    return None


def _read_png_size(header: bytes) -> tuple[int, int] | None:
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _read_gif_size(header: bytes) -> tuple[int, int] | None:
    if len(header) < 10 or not (header.startswith(b"GIF87a") or header.startswith(b"GIF89a")):
        return None
    width = int.from_bytes(header[6:8], "little")
    height = int.from_bytes(header[8:10], "little")
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _read_webp_size(file_path: str, header: bytes) -> tuple[int, int] | None:
    if len(header) < 16 or not header.startswith(b"RIFF") or header[8:12] != b"WEBP":
        return None
    with open_binary(file_path, mode="rb") as file_handle:
        file_handle.seek(12)
        while True:
            chunk_header = file_handle.read(8)
            if len(chunk_header) < 8:
                return None
            chunk_type = chunk_header[0:4]
            chunk_size = int.from_bytes(chunk_header[4:8], "little")
            if chunk_size < 0:
                return None
            if chunk_type in (b"VP8 ", b"VP8L", b"VP8X"):
                data = file_handle.read(chunk_size)
                if len(data) < chunk_size:
                    return None
                if chunk_type == b"VP8 " and len(data) >= 10 and (data[3:6] == b"\x9d\x01*"):
                    width = struct.unpack_from("<H", data, 6)[0] & 16383
                    height = struct.unpack_from("<H", data, 8)[0] & 16383
                    if width > 0 and height > 0:
                        return (width, height)
                elif chunk_type == b"VP8L" and len(data) >= 5 and (data[0] == 47):
                    width = 1 + (data[1] | (data[2] & 63) << 8)
                    height = 1 + (data[2] >> 6 | data[3] << 2 | (data[4] & 15) << 10)
                    if width > 0 and height > 0:
                        return (width, height)
                elif chunk_type == b"VP8X" and len(data) >= 10:
                    width = 1 + int.from_bytes(data[4:7], "little")
                    height = 1 + int.from_bytes(data[7:10], "little")
                    if width > 0 and height > 0:
                        return (width, height)
            else:
                file_handle.seek(chunk_size, os.SEEK_CUR)
            if chunk_size % 2 == 1:
                file_handle.seek(1, os.SEEK_CUR)


def _read_jpeg_size(file_path: str) -> tuple[int, int] | None:
    sof_markers = {192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207}
    with open_binary(file_path, mode="rb") as file_handle:
        if file_handle.read(2) != b"\xff\xd8":
            return None
        while True:
            marker_prefix = file_handle.read(1)
            if not marker_prefix:
                return None
            if marker_prefix != b"\xff":
                return None
            marker = file_handle.read(1)
            if not marker:
                return None
            marker_value = marker[0]
            if marker_value == 217:
                return None
            while marker == b"\xff":
                marker = file_handle.read(1)
                if not marker:
                    return None
                marker_value = marker[0]
                if marker_value == 217:
                    return None
            if marker_value in (1, 208, 209, 210, 211, 212, 213, 214, 215):
                continue
            length_bytes = file_handle.read(2)
            if len(length_bytes) != 2:
                return None
            segment_length = int.from_bytes(length_bytes, "big")
            if segment_length < 2:
                return None
            if marker_value in sof_markers:
                data = file_handle.read(segment_length - 2)
                if len(data) < 5:
                    return None
                height = int.from_bytes(data[1:3], "big")
                width = int.from_bytes(data[3:5], "big")
                if width > 0 and height > 0:
                    return (width, height)
                return None
            file_handle.seek(segment_length - 2, os.SEEK_CUR)
