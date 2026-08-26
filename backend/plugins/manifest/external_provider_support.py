"""SoAI - Plugin external provider support resolution [backend/plugins/manifest/external_provider_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.openai.compatibility import ExternalProviderMode

__all__ = ("resolve_external_provider_support",)


def resolve_external_provider_support(
    provider_mode: ExternalProviderMode,
    supports_external_providers: bool,
) -> bool:
    if provider_mode == ExternalProviderMode.NONE and supports_external_providers:
        raise ValidationError(
            "Plugin contract violation: SUPPORTS_EXTERNAL_PROVIDERS=True requires EXTERNAL_PROVIDER_MODE to be USER_MANAGED.",
        )
    if provider_mode == ExternalProviderMode.USER_MANAGED:
        if not supports_external_providers:
            raise ValidationError(
                "Plugin contract violation: EXTERNAL_PROVIDER_MODE=USER_MANAGED requires SUPPORTS_EXTERNAL_PROVIDERS=True.",
            )
        return True
    if provider_mode == ExternalProviderMode.PLUGIN_MANAGED:
        if supports_external_providers:
            raise ValidationError(
                "Plugin contract violation: EXTERNAL_PROVIDER_MODE=PLUGIN_MANAGED requires SUPPORTS_EXTERNAL_PROVIDERS=False.",
            )
        return False
    return supports_external_providers
