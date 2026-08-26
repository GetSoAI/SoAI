"""SoAI - Preview-contract retry settings resolution [backend/features/api/runtime/preview_contract_retry_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol

__all__ = ("resolve_preview_contract_max_retries",)

_CONFIG_KEY_MAX_RETRIES = "SERVER.WEBUI.PREVIEW_CONTRACT.MAX_RETRIES"
_MAX_ALLOWED_RETRIES = 10


def resolve_preview_contract_max_retries(config: ConfigProtocol) -> int:
    raw = config.get_int(_CONFIG_KEY_MAX_RETRIES)
    return max(0, min(raw, _MAX_ALLOWED_RETRIES))
