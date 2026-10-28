"""SoAI - Apache Tika distribution identity [backend/core/bootstrap/tika_runtime_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "TIKA_BUNDLED_DISTRIBUTION_SHA512",
    "TIKA_DISTRIBUTION_NAME",
    "TIKA_DISTRIBUTION_SHA512",
    "TIKA_DISTRIBUTION_URL",
    "TIKA_EXPECTED_VERSION",
    "TIKA_SERVER_CONFIG",
    "TIKA_SERVER_CONFIG_NAME",
    "TIKA_SERVER_JAR_NAME",
    "TIKA_SERVER_JAR_SHA512",
    "TIKA_SERVER_VERSION",
)

TIKA_SERVER_VERSION = "4.1.0"
TIKA_EXPECTED_VERSION = "Apache Tika 4.1.0"
TIKA_DISTRIBUTION_NAME = "tika-server-standard-4.1.0.zip"
TIKA_SERVER_JAR_NAME = "tika-server-standard-4.1.0.jar"
TIKA_DISTRIBUTION_URL = "https://archive.apache.org/dist/tika/4.1.0/tika-server-standard-4.1.0.zip"
TIKA_BUNDLED_DISTRIBUTION_SHA512 = "c5172bb44eafeee41c0160fc3ac01abedc3ebe79fb3ac582dbdacb85d244a1ae45db18d8c6b48a5e9ed35656823f393c5d485e1c57fe4b722aa31774cfef253b"  # pragma: allowlist secret
TIKA_DISTRIBUTION_SHA512 = "c932f84c569fb02df4f72ab060d6f2cf77b6797417040202401bc256e18a8f6f0ebc25d12d6dce222cb9328abfcb388cfa6511d7382c765a45687240a8a4bd7e"  # pragma: allowlist secret
TIKA_SERVER_JAR_SHA512 = "0eb0ebebcaeebd223e2f38f18288c8328d86125846801fe3117cbe81ffadb33060fabd6f36ff38889a5c8b73a10e085581346e89f0967216b26d556abc050f6e"  # pragma: allowlist secret
TIKA_SERVER_CONFIG_NAME = "server-config.json"
TIKA_SERVER_CONFIG = (
    '{"server":{"allowPerRequestConfig":true},"pipes":{"numClients":1},'
    '"metadata-filters":[{"legacy-key-migration-filter":{}}],'
    '"parsers":[{"default-parser":{}},{"office-parser":{"writeSelectHeadersInBody":true}}]}\n'
)
