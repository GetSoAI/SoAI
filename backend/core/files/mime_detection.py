"""SoAI - Buffered MIME detection helpers [backend/core/files/mime_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.image_signature import validate_image_signature
from core.files.text_extensions import resolve_text_file_content_type_from_extension

__all__ = (
    "LocalMimeDetector",
    "create_mime_detector",
    "detect_mime_type",
)

_ARCHIVE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b", "application/x-gzip"),
    (b"BZh", "application/x-bzip2"),
    (b"\xfd7zXZ\x00", "application/x-xz"),
    (b"Rar!\x1a\x07\x00", "application/x-rar-compressed"),
    (b"Rar!\x1a\x07\x01", "application/x-rar-compressed"),
    (b"7z\xbc\xaf'\x1c", "application/x-7z-compressed"),
    (b"(\xb5/\xfd", "application/zstd"),
)
_OLE_SIGNATURE: bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_JSON_PREFIXES: tuple[bytes, ...] = (b"{", b"[")
_XML_PREFIXES: tuple[bytes, ...] = (b"<?xml", b"<rss", b"<feed", b"<rdf", b"<svg")
_HTML_TOKENS: tuple[bytes, ...] = (b"<!doctype html", b"<html", b"<body", b"<head")
_FTYP_AUDIO_BRANDS: frozenset[str] = frozenset(("f4a ", "m4a ", "m4b ", "m4p "))
_FTYP_HEIC_BRANDS: frozenset[str] = frozenset(("heic", "heix", "hevc", "hevx", "heim", "heis"))
_FTYP_HEIF_BRANDS: frozenset[str] = frozenset(("mif1", "msf1"))


class LocalMimeDetector:
    def from_buffer(self, buf: bytes) -> str:
        return detect_mime_type(buf) or ""


def create_mime_detector() -> LocalMimeDetector:
    return LocalMimeDetector()


def detect_mime_type(data: bytes, *, filename: str | None = None) -> str | None:
    extension = _normalize_extension(filename)
    if not data:
        return None
    image_valid, image_mime_type = validate_image_signature(data)
    if image_valid:
        return image_mime_type
    riff_mime_type = _detect_riff_mime_type(data)
    if riff_mime_type is not None:
        return riff_mime_type
    for signature, mime_type in _ARCHIVE_SIGNATURES:
        if data.startswith(signature):
            if mime_type == "application/zip":
                office_zip_mime_type = _office_zip_extension_mime_type(extension)
                return office_zip_mime_type if office_zip_mime_type is not None else mime_type
            return mime_type
    if data.startswith(_OLE_SIGNATURE):
        office_ole_mime_type = _office_ole_extension_mime_type(extension)
        if office_ole_mime_type is not None:
            return office_ole_mime_type
    if _looks_like_flac(data):
        return "audio/flac"
    if _looks_like_ogg(data):
        return _mime_type_from_extension(extension, include_text=False) or "audio/ogg"
    if _looks_like_mp3(data):
        return "audio/mpeg"
    if _looks_like_aac(data):
        return "audio/aac"
    mp4_like_mime_type = _detect_mp4_like_mime_type(data, extension)
    if mp4_like_mime_type is not None:
        return mp4_like_mime_type
    if _looks_like_json(data):
        return "application/json"
    if _looks_like_xml(data):
        return "application/xml"
    if _looks_like_html(data):
        return "text/html"
    if _looks_like_text(data):
        return _mime_type_from_extension(extension, include_text=True) or "text/plain"
    return _mime_type_from_extension(extension, include_text=False)


def _normalize_extension(filename: str | None) -> str:
    if not isinstance(filename, str) or not filename.strip():
        return ""
    _root, extension = os.path.splitext(filename.strip().lower())
    return extension


def _mime_type_from_extension(extension: str, *, include_text: bool) -> str | None:
    if not extension:
        return None
    if include_text:
        text_mime_type = _text_extension_mime_type(extension)
        if text_mime_type is not None:
            return text_mime_type
    audio_mime_type = _audio_extension_mime_type(extension)
    if audio_mime_type is not None:
        return audio_mime_type
    image_mime_type = _image_extension_mime_type(extension)
    if image_mime_type is not None:
        return image_mime_type
    office_zip_mime_type = _office_zip_extension_mime_type(extension)
    if office_zip_mime_type is not None:
        return office_zip_mime_type
    office_ole_mime_type = _office_ole_extension_mime_type(extension)
    if office_ole_mime_type is not None:
        return office_ole_mime_type
    return None


def _text_extension_mime_type(extension: str) -> str | None:
    return resolve_text_file_content_type_from_extension(extension)


def _audio_extension_mime_type(extension: str) -> str | None:
    match extension:
        case ".wav":
            return "audio/wav"
        case ".mp3":
            return "audio/mpeg"
        case ".m4a":
            return "audio/mp4"
        case ".ogg":
            return "audio/ogg"
        case ".flac":
            return "audio/flac"
        case ".webm":
            return "audio/webm"
        case ".aac":
            return "audio/aac"
        case _:
            return None


def _image_extension_mime_type(extension: str) -> str | None:
    match extension:
        case ".bmp":
            return "image/bmp"
        case ".tif" | ".tiff":
            return "image/tiff"
        case ".heic":
            return "image/heic"
        case ".heif":
            return "image/heif"
        case _:
            return None


def _office_zip_extension_mime_type(extension: str) -> str | None:
    match extension:
        case ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        case ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        case ".pptx":
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        case ".epub":
            return "application/epub+zip"
        case ".jar":
            return "application/java-archive"
        case _:
            return None


def _office_ole_extension_mime_type(extension: str) -> str | None:
    match extension:
        case ".doc":
            return "application/msword"
        case ".xls":
            return "application/vnd.ms-excel"
        case ".ppt":
            return "application/vnd.ms-powerpoint"
        case _:
            return None


def _detect_riff_mime_type(data: bytes) -> str | None:
    if len(data) < 12 or not data.startswith(b"RIFF"):
        return None
    riff_type = data[8:12]
    if riff_type == b"WEBP":
        return "image/webp"
    if riff_type == b"WAVE":
        return "audio/wav"
    return None


def _looks_like_flac(data: bytes) -> bool:
    return data.startswith(b"fLaC")


def _looks_like_ogg(data: bytes) -> bool:
    return data.startswith(b"OggS")


def _looks_like_mp3(data: bytes) -> bool:
    if data.startswith(b"ID3"):
        return True
    if len(data) < 2:
        return False
    return data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def _looks_like_aac(data: bytes) -> bool:
    if len(data) < 2:
        return False
    if data.startswith(b"ADIF"):
        return True
    return data[0] == 0xFF and (data[1] & 0xF6) == 0xF0


def _detect_mp4_like_mime_type(data: bytes, extension: str) -> str | None:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return None
    brand = data[8:12].decode("latin-1").lower()
    if brand in _FTYP_HEIC_BRANDS:
        return "image/heic"
    if brand in _FTYP_HEIF_BRANDS:
        return "image/heif"
    if brand in _FTYP_AUDIO_BRANDS:
        return "audio/mp4"
    extension_mime_type = _mime_type_from_extension(extension, include_text=False)
    if extension_mime_type is not None:
        return extension_mime_type
    return None


def _looks_like_json(data: bytes) -> bool:
    stripped = data.lstrip()
    return stripped.startswith(_JSON_PREFIXES)


def _looks_like_xml(data: bytes) -> bool:
    stripped = data[:512].lstrip().lower()
    return any(stripped.startswith(prefix) for prefix in _XML_PREFIXES)


def _looks_like_html(data: bytes) -> bool:
    stripped = data[:512].lower()
    return any(token in stripped for token in _HTML_TOKENS)


def _looks_like_text(data: bytes) -> bool:
    sample = data[:1024]
    if not sample:
        return False
    if b"\x00" in sample:
        return False
    printable_count = sum(
        1 for byte_value in sample if 32 <= byte_value <= 126 or byte_value in (9, 10, 13)
    )
    return (printable_count / len(sample)) >= 0.8
