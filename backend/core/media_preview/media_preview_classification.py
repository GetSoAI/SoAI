"""SoAI - WebUI media type classification and provider parsing [backend/core/media_preview/media_preview_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from core.files.content_types import (
    content_type_is_audio,
    content_type_is_document,
    content_type_is_html,
    content_type_is_image,
    content_type_is_text,
    content_type_is_video,
    normalize_content_type,
)

__all__ = (
    "MEDIA_TYPE_AUDIO",
    "MEDIA_TYPE_DOCUMENT",
    "MEDIA_TYPE_EMBED",
    "MEDIA_TYPE_FILE",
    "MEDIA_TYPE_IMAGE",
    "MEDIA_TYPE_LINK",
    "MEDIA_TYPE_TEXT",
    "MEDIA_TYPE_VIDEO",
    "YOUTUBE_DOMAINS",
    "classify_content_type_for_link_preview",
    "classify_media_type_for_extension",
    "classify_mime_type_for_file_preview",
    "classify_url_by_extension",
    "mime_for_extension",
    "normalize_content_type",
    "normalize_host_for_matching",
    "try_parse_youtube_embed",
)

MEDIA_TYPE_IMAGE: Literal["image"] = "image"
MEDIA_TYPE_AUDIO: Literal["audio"] = "audio"
MEDIA_TYPE_VIDEO: Literal["video"] = "video"
MEDIA_TYPE_TEXT: Literal["text"] = "text"
MEDIA_TYPE_DOCUMENT: Literal["document"] = "document"
MEDIA_TYPE_FILE: Literal["file"] = "file"
MEDIA_TYPE_EMBED: Literal["embed"] = "embed"
MEDIA_TYPE_LINK: Literal["link"] = "link"

YOUTUBE_DOMAINS: tuple[str, ...] = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
EXT_DOCUMENT: frozenset[str] = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".rtf",
        ".odt",
        ".ods",
        ".odp",
    },
)


def mime_for_extension(extension: str) -> str | None:
    ext = (extension or "").strip().lower()
    match ext:
        case ".png":
            return "image/png"
        case ".jpg" | ".jpeg":
            return "image/jpeg"
        case ".gif":
            return "image/gif"
        case ".webp":
            return "image/webp"
        case ".avif":
            return "image/avif"
        case ".bmp":
            return "image/bmp"
        case ".mp3":
            return "audio/mpeg"
        case ".wav":
            return "audio/wav"
        case ".ogg":
            return "audio/ogg"
        case ".m4a":
            return "audio/mp4"
        case ".flac":
            return "audio/flac"
        case ".mp4":
            return "video/mp4"
        case ".webm":
            return "video/webm"
        case ".mov":
            return "video/quicktime"
        case ".mkv":
            return "video/x-matroska"
        case _:
            return None


def classify_media_type_for_extension(extension: str) -> str | None:
    ext = (extension or "").strip().lower()
    mime = mime_for_extension(ext)
    if mime is not None:
        top_level_type = mime.split("/", 1)[0]
        match top_level_type:
            case "image":
                return MEDIA_TYPE_IMAGE
            case "audio":
                return MEDIA_TYPE_AUDIO
            case "video":
                return MEDIA_TYPE_VIDEO
            case _:
                return MEDIA_TYPE_FILE
    if ext in EXT_DOCUMENT:
        return MEDIA_TYPE_DOCUMENT
    if ext in {".txt", ".md", ".csv", ".json", ".xml"}:
        return MEDIA_TYPE_TEXT
    return None


def normalize_host_for_matching(host: str) -> str:
    value = (host or "").strip().lower()
    return value.removeprefix("www.")


def file_extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if not path:
        return ""
    last_segment = path.rsplit("/", 1)[-1]
    if "." not in last_segment:
        return ""
    return f".{last_segment.rsplit('.', 1)[-1]}".lower()


def classify_url_by_extension(normalized_url: str) -> tuple[str, str | None]:
    ext = file_extension_from_url(normalized_url)
    media_type = classify_media_type_for_extension(ext)
    if media_type is not None:
        mime = mime_for_extension(ext)
        if (
            media_type in {MEDIA_TYPE_IMAGE, MEDIA_TYPE_AUDIO, MEDIA_TYPE_VIDEO}
            and mime is not None
        ):
            return (media_type, mime)
        if media_type == MEDIA_TYPE_TEXT:
            return (media_type, "text/plain; charset=utf-8")
        if media_type == MEDIA_TYPE_DOCUMENT:
            return (media_type, None)
        return (media_type, mime)
    return (MEDIA_TYPE_LINK, None)


def classify_content_type_for_link_preview(content_type: str | None) -> str | None:
    normalized = normalize_content_type(content_type)
    if not normalized:
        return None
    if content_type_is_html(normalized):
        return None
    if content_type_is_image(normalized):
        return MEDIA_TYPE_IMAGE
    if content_type_is_audio(normalized):
        return MEDIA_TYPE_AUDIO
    if content_type_is_video(normalized):
        return MEDIA_TYPE_VIDEO
    if content_type_is_text(normalized):
        return MEDIA_TYPE_TEXT
    if content_type_is_document(normalized):
        return MEDIA_TYPE_DOCUMENT
    return MEDIA_TYPE_FILE


def classify_mime_type_for_file_preview(
    mime_type: str | None,
) -> Literal["image", "audio", "video", "text", "document", "file"]:
    normalized = normalize_content_type(mime_type)
    if content_type_is_image(normalized):
        return MEDIA_TYPE_IMAGE
    if content_type_is_audio(normalized):
        return MEDIA_TYPE_AUDIO
    if content_type_is_video(normalized):
        return MEDIA_TYPE_VIDEO
    if content_type_is_text(normalized):
        return MEDIA_TYPE_TEXT
    if content_type_is_document(normalized):
        return MEDIA_TYPE_DOCUMENT
    return MEDIA_TYPE_FILE


def try_parse_youtube_embed(normalized_url: str) -> tuple[str, str] | None:
    parsed = urlparse(normalized_url)
    host = normalize_host_for_matching(parsed.hostname or "")
    allowed_hosts = tuple(normalize_host_for_matching(domain) for domain in YOUTUBE_DOMAINS)
    if host not in allowed_hosts:
        return None
    video_id = ""
    if host == "youtu.be":
        video_id = (parsed.path or "").lstrip("/").split("/", 1)[0]
    else:
        path_parts = [part for part in (parsed.path or "").split("/") if part]
        if path_parts:
            if path_parts[0] == "watch":
                query = parsed.query or ""
                match = re.search(r"(?:^|&)v=([^&]+)", query)
                if match:
                    video_id = match.group(1)
            elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed"}:
                video_id = path_parts[1]
    video_id = (video_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None
    embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}"
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return (embed_url, thumb_url)
