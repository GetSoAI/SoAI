"""SoAI - Media preview settings resolution helpers [backend/core/media_preview/media_preview_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.numeric_lenient import coerce_lenient_bounded_float
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError

__all__ = (
    "MediaPreviewSettings",
    "resolve_media_preview_settings",
)


@dataclass(frozen=True, slots=True)
class MediaPreviewSettings:
    cache_storage_path: str
    max_fetch_size_bytes: int
    cache_max_size_bytes: int
    max_redirects: int
    timeout_sec: float
    dns_timeout_sec: float
    block_private_networks: bool
    text_preview_max_bytes: int
    preview_client_cache_ttl_sec: int


def _require_non_empty_string(value: str | None, *, field: str) -> str:
    if value is None:
        raise ConfigurationError(f"{field} is missing in config.yaml.")
    stripped = value.strip()
    if not stripped:
        raise ConfigurationError(f"{field} is missing or invalid in config.yaml.")
    return stripped


def _resolve_size_mb(config: ConfigProtocol, field: str) -> int:
    return require_config_mib_to_bytes(
        config.get(field),
        field=field,
        missing_message=f"{field} is missing in config.yaml.",
        invalid_message=f"{field} must be a valid integer in config.yaml.",
        positive_message=f"{field} must be greater than zero.",
    )


def _resolve_text_preview_max_bytes(config: ConfigProtocol) -> int:
    field = "SERVER.WEBUI.MEDIA_PREVIEWS.TEXT_PREVIEW_MAX_BYTES"
    invalid_message = f"{field} must be a valid integer in config.yaml."
    raw = config.get(field)
    if raw is None:
        raise ConfigurationError(f"{field} is missing in config.yaml.")
    if isinstance(raw, bool):
        raise ConfigurationError(invalid_message)
    if isinstance(raw, int | float):
        parsed = int(raw)
    elif isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            raise ConfigurationError(invalid_message)
        try:
            parsed = int(stripped)
        except ValueError as exception:
            raise ConfigurationError(invalid_message) from exception
    else:
        raise ConfigurationError(invalid_message)
    if parsed <= 0:
        raise ConfigurationError(f"{field} must be greater than zero.")
    return parsed


def resolve_media_preview_settings(config: ConfigProtocol) -> MediaPreviewSettings:
    cache_storage_path = _require_non_empty_string(
        config.get_str("SERVER.WEBUI.MEDIA_PREVIEWS.CACHE_STORAGE_PATH"),
        field="SERVER.WEBUI.MEDIA_PREVIEWS.CACHE_STORAGE_PATH",
    )
    timeout_sec = config.get_float("SERVER.WEBUI.MEDIA_PREVIEWS.TIMEOUT_SEC")
    max_redirects = config.get_int("SERVER.WEBUI.MEDIA_PREVIEWS.MAX_REDIRECTS")
    block_private_networks = config.get_bool("SERVER.WEBUI.MEDIA_PREVIEWS.BLOCK_PRIVATE_NETWORKS")
    return MediaPreviewSettings(
        cache_storage_path=cache_storage_path,
        max_fetch_size_bytes=_resolve_size_mb(
            config,
            "SERVER.WEBUI.MEDIA_PREVIEWS.MAX_FETCH_SIZE_MB",
        ),
        cache_max_size_bytes=_resolve_size_mb(
            config,
            "SERVER.WEBUI.MEDIA_PREVIEWS.CACHE_MAX_SIZE_MB",
        ),
        max_redirects=max(0, min(max_redirects, 25)),
        timeout_sec=max(0.5, min(timeout_sec, 120.0)),
        dns_timeout_sec=coerce_lenient_bounded_float(
            config.get("SERVER.WEBUI.MEDIA_PREVIEWS.DNS_TIMEOUT_SEC"),
            default=3.0,
            minimum=0.5,
            maximum=30.0,
        ),
        block_private_networks=bool(block_private_networks),
        text_preview_max_bytes=_resolve_text_preview_max_bytes(config),
        preview_client_cache_ttl_sec=max(
            0,
            min(
                config.get_int("SERVER.WEBUI.MEDIA_PREVIEWS.PREVIEW_CLIENT_CACHE_TTL_SEC"),
                31_536_000,
            ),
        ),
    )
