"""SoAI - Unified server startup settings [backend/app/server_startup_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.application_dependencies import ApplicationServerModuleDependencies
from core.config.runtime_config import Config

__all__ = (
    "UnifiedServerStartupSettings",
    "resolve_unified_server_startup_settings",
)


@dataclass(frozen=True, slots=True)
class UnifiedServerStartupSettings:
    host: str
    port: int
    scheme: str
    transport_layer_security_options: dict[str, str | int]
    user_supplied_transport_layer_security: bool


def resolve_unified_server_startup_settings(
    configuration: Config,
    module_dependencies: ApplicationServerModuleDependencies,
) -> UnifiedServerStartupSettings:
    host = configuration.require_str("SERVER.HTTP.NETWORK.HOST")
    port = configuration.get_int("SERVER.HTTP.NETWORK.PORT")
    (
        transport_layer_security_options,
        user_supplied_transport_layer_security,
    ) = module_dependencies.prepare_tls_configuration(configuration)
    scheme = "https" if transport_layer_security_options else "http"
    return UnifiedServerStartupSettings(
        host=host,
        port=port,
        scheme=scheme,
        transport_layer_security_options=transport_layer_security_options,
        user_supplied_transport_layer_security=user_supplied_transport_layer_security,
    )
