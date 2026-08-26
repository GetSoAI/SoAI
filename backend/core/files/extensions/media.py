"""SoAI - Media file extension constants [backend/core/files/extensions/media.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

IMAGE_EXTENSIONS = frozenset(
    (
        "png",
        "jpg",
        "jpeg",
        "jpe",
        "gif",
        "bmp",
        "dib",
        "tiff",
        "tif",
        "webp",
        "avif",
        "ico",
        "icns",
        "j2k",
        "jp2",
        "jpx",
        "pcx",
        "ppm",
        "pbm",
        "pgm",
        "pnm",
        "tga",
        "sgi",
        "qoi",
        "dds",
        "psd",
        "mpo",
        "heic",
        "heif",
    ),
)

AUDIO_EXTENSIONS = frozenset(
    (
        "mp3",
        "wav",
        "flac",
        "ogg",
        "aac",
        "m4a",
        "wma",
        "aiff",
        "aif",
        "ape",
        "opus",
        "oga",
        "wv",
        "mka",
    ),
)

VIDEO_EXTENSIONS = frozenset(
    (
        "mp4",
        "mkv",
        "avi",
        "mov",
        "wmv",
        "flv",
        "webm",
        "m4v",
        "mpg",
        "mpeg",
        "vob",
        "ogv",
        "m2ts",
        "mts",
        "3gp",
        "3g2",
        "asf",
        "rm",
        "rmvb",
        "divx",
        "xvid",
        "f4v",
        "f4p",
        "m2v",
        "mpv",
        "mpe",
        "m1v",
        "qt",
        "h264",
    ),
)
