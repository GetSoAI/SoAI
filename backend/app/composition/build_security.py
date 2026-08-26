"""SoAI - Application security service assembly [backend/app/composition/build_security.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.application_dependencies import ApplicationSecurity
from core.config.protocols import ConfigProtocol
from core.security.encryption import load_or_create_encryption_keyring
from features.api.runtime.container.auth_config import AuthConfig

__all__ = ("build_security_services",)


def build_security_services(
    *,
    config: ConfigProtocol,
) -> ApplicationSecurity:
    keyring = load_or_create_encryption_keyring(config)
    return ApplicationSecurity(
        fernet=keyring.fernet,
        primary_signing_secret=keyring.primary_authentication_secret,
        verification_secrets=keyring.authentication_secrets,
        auth_config=AuthConfig(),
    )
