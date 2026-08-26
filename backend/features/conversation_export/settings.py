"""SoAI - Conversation PDF export settings [backend/features/conversation_export/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.byte_sizes import MIB_BYTES
from core.config.numeric import coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.meta.paths import get_repo_root, join_data_abs
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC

__all__ = (
    "ConversationPdfExportSettings",
    "resolve_conversation_pdf_export_settings",
)

_RETENTION_RENDER_TIMEOUT_MULTIPLIER = 2


@dataclass(frozen=True, slots=True)
class ConversationPdfExportSettings:
    temp_dir: str
    max_html_bytes: int
    max_pdf_bytes: int
    render_timeout_sec: int
    max_active_per_user: int
    max_active_global: int
    artifact_retention_sec: int


def _config_int(
    config: ConfigProtocol,
    key: str,
    *,
    default: int,
    minimum: int,
) -> int:
    value = config.get(key, default)
    return coerce_positive_int(value, default=default, minimum=minimum)


def _resolve_artifact_retention_sec(config: ConfigProtocol, render_timeout_sec: int) -> int:
    configured = _config_int(
        config,
        "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.ARTIFACT_RETENTION_SEC",
        default=2 * LONG_IDLE_TIMEOUT_SEC,
        minimum=LONG_IDLE_TIMEOUT_SEC,
    )
    render_floor = render_timeout_sec * _RETENTION_RENDER_TIMEOUT_MULTIPLIER + LONG_IDLE_TIMEOUT_SEC
    return max(configured, render_floor)


def resolve_conversation_pdf_export_settings(
    config: ConfigProtocol,
) -> ConversationPdfExportSettings:
    render_timeout_sec = _config_int(
        config,
        "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.RENDER_TIMEOUT_SEC",
        default=900,
        minimum=30,
    )
    return ConversationPdfExportSettings(
        temp_dir=join_data_abs(get_repo_root(), "temp", "conversation-pdf-exports"),
        max_html_bytes=_config_int(
            config,
            "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.MAX_HTML_BYTES",
            default=512 * MIB_BYTES,
            minimum=1 * MIB_BYTES,
        ),
        max_pdf_bytes=_config_int(
            config,
            "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.MAX_PDF_BYTES",
            default=1024 * MIB_BYTES,
            minimum=1 * MIB_BYTES,
        ),
        render_timeout_sec=render_timeout_sec,
        max_active_per_user=_config_int(
            config,
            "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.MAX_ACTIVE_PER_USER",
            default=1,
            minimum=1,
        ),
        max_active_global=_config_int(
            config,
            "SERVER.WEBUI.CONVERSATION_PDF_EXPORT.MAX_ACTIVE_GLOBAL",
            default=2,
            minimum=1,
        ),
        artifact_retention_sec=_resolve_artifact_retention_sec(config, render_timeout_sec),
    )
