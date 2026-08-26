"""SoAI - Default config schema: system API [backend/core/config/default_schema/system_api.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_system_api_defaults",)


def _build_http_config() -> ConfigDict:
    return {
        "ENABLED": True,
        "LOG_STREAM": {
            "TIMEOUT_SEC": 30,
            "BATCH_SIZE": 50,
            "INTERVAL_MS": 200,
        },
        "NETWORK": {
            "HOST": "0.0.0.0",
            "PORT": 5090,
            "DISCOVERY_HOST": "0.0.0.0",
            "SHUTDOWN_TIMEOUT_SEC": 10,
        },
        "CORS": {
            "ALLOWED_ORIGINS": [],
            "ALLOW_CREDENTIALS": True,
            "MAX_AGE_SEC": 3600,
        },
        "PROXY": {
            "ENABLE_HEADERS": False,
            "TRUSTED_NETWORKS": [],
        },
        "ACCESS_CONTROL": {
            "IP_WHITELIST": [],
            "IP_BLACKLIST": [],
        },
        "SSL": {
            "TLS_ENABLED": False,
            "CERT_FILE": "",
            "KEY_FILE": "",
            "CA_FILE": "",
            "KEY_PASSWORD": "",
        },
        "SECURITY": {
            "REQUIRE_SECURE_TRANSPORT": False,
            "FORCE_HTTPS_REDIRECT": False,
            "ENFORCE_HSTS": True,
            "ENFORCE_UPGRADE_INSECURE_REQUESTS": False,
        },
        "REQUEST_BODY": {
            "OPENAI_MAX_BYTES": mib_to_bytes(256),
            "NATIVE_MAX_BYTES": mib_to_bytes(16),
            "READ_DEADLINE_SEC": 120.0,
        },
        "STREAMING": {
            "STREAM_INACTIVITY_TIMEOUT_SEC": 300.0,
            "REPLAY_BUFFER_SIZE": 1000,
            "POST_TERMINAL_CHANNEL_RETENTION_SEC": 300.0,
            "RESPONSES_PERSIST_FLUSH_INTERVAL_MS": 100,
            "RESPONSES_PERSIST_MAX_EVENTS_PER_FLUSH": 250,
            "RESPONSES_PERSIST_MAX_PENDING_EVENTS": 5000,
        },
    }


def build_system_api_defaults() -> ConfigDict:
    http_config = _build_http_config()
    return {
        "PUBLIC_ORIGIN": "",
        "HTTP": http_config,
    }
