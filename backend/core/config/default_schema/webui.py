"""SoAI - WebUI configuration defaults [backend/core/config/default_schema/webui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_webui_defaults",)


def build_webui_defaults() -> ConfigDict:
    return {
        "WEBUI": {
            "ENABLED": True,
            "PATH": "frontend",
            "FALLBACK_PATHS": [],
            "ACCESS_TOKEN_EXPIRE_MINUTES": 43_200,
            "COOKIE_SECURE": False,
            "WALLPAPER_MAX_SIZE_MB": 25,
            "WALLPAPER_STORAGE_PATH": "wallpaper",
            "WALLPAPER_DOWNLOAD": {
                "BLOCK_PRIVATE_NETWORKS": True,
                "DNS_TIMEOUT_SEC": 3.0,
                "MAX_REDIRECTS": 10,
            },
            "MEDIA_PREVIEWS": {
                "CACHE_STORAGE_PATH": "webui_media_previews_cache",
                "MAX_FETCH_SIZE_MB": 100,
                "CACHE_MAX_SIZE_MB": 200,
                "MAX_REDIRECTS": 10,
                "TIMEOUT_SEC": 30.0,
                "DNS_TIMEOUT_SEC": 3.0,
                "BLOCK_PRIVATE_NETWORKS": True,
                "TEXT_PREVIEW_MAX_BYTES": 32_768,
                "PREVIEW_CLIENT_CACHE_TTL_SEC": 31_536_000,
            },
            "AUTO_OPEN_BROWSER": True,
            "NOTIFICATIONS": {
                "EMIT_ON_AUTOMATION_COMPLETE": True,
                "MAX_PER_USER": 1000,
            },
            "TERMINAL": {
                "ENABLED": True,
            },
            "CHAT": {
                "CAMERA_VISION_UPLOAD_ENABLED": True,
                "CAMERA_VISION_IMAGE_OPTIMIZATION_ENABLED": True,
            },
            "PROVIDER_TEXT": {
                "MAX_STORE_CHARS": 2_000_000,
                "MIN_CHARS": 20_000,
                "CONTEXT_FRACTION": 0.30,
                "CHAR_TO_TOKEN_RATIO": 4,
                "RESERVED_OUTPUT_TOKENS": 2048,
                "UPLOAD_PARSE_TIMEOUT_SEC": 120,
            },
            "PROVIDER_IMAGE": {
                "MAX_SOURCE_BYTES": mib_to_bytes(128),
                "MAX_ENCODED_CHARS": mib_to_bytes(16),
                "MAX_PIXELS": 4_000_000,
                "JPEG_QUALITY": 85,
            },
            "PROVIDER_VIDEO": {
                "MAX_FRAMES_PER_REQUEST": 12,
                "MAX_ENCODED_CHARS_PER_REQUEST": mib_to_bytes(16),
                "PROJECTION_TIMEOUT_SEC": 120,
                "MAX_CONCURRENT_PROJECTIONS": 2,
            },
            "SOAI_LINKS": {
                "RESOLVE_MAX_TOKENS": 64,
                "RESOLVE_MAX_DISTINCT_PATHS": 32,
                "RESOLVE_CONCURRENT_REQUESTS_PER_CONVERSATION": 2,
                "PROJECTION_FOLDER_MAX_ENTRIES": 20,
                "PROJECTION_FOLDER_MAX_CHARS": 12_000,
                "PROJECTION_READ_TIMEOUT_SEC": 30,
            },
            "KNOWLEDGE_LINKS": {
                "USE_MAX_ITEMS": 100,
            },
            "PREVIEW_CONTRACT": {
                "MAX_RETRIES": 2,
            },
            "LOGIN_SECURITY": {
                "MAX_BODY_BYTES": 8192,
                "AUTH_FAILURE_RATELIMIT": {
                    "WINDOW_SECONDS": 300,
                    "MAX_FAILURES": 10,
                },
                "ADMIN_ALERTS": {
                    "ENABLED": True,
                    "COOLDOWN_SECONDS": 900,
                },
            },
        },
    }
