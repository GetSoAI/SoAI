"""SoAI - Managed Java runtime asset definitions and catalog [backend/core/bootstrap/java_runtime_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from dataclasses import dataclass

__all__ = (
    "JAVA_RUNTIME_PROVIDER",
    "JAVA_RUNTIME_RELEASE",
    "JAVA_RUNTIME_RELEASE_DIR",
    "JavaRuntimeAsset",
    "get_java_runtime_assets",
)

JAVA_RUNTIME_PROVIDER = "azul-zulu"
JAVA_RUNTIME_RELEASE = "17.0.21+9"
JAVA_RUNTIME_RELEASE_DIR = "17.70.111"


@dataclass(frozen=True, slots=True)
class JavaRuntimeAsset:
    platform_id: str
    url: str
    sha256: str
    filename: str
    archive_format: str


@functools.cache
def get_java_runtime_assets() -> dict[str, JavaRuntimeAsset]:
    return {
        "linux-x64": JavaRuntimeAsset(
            platform_id="linux-x64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-linux_x64.tar.gz",
            sha256="730ac4f645f601d3005bcdc8736c7e0630d402382e332c11d61ac2494436587f",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-linux_x64.tar.gz",
            archive_format="tar.gz",
        ),
        "linux-arm64": JavaRuntimeAsset(
            platform_id="linux-arm64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-linux_aarch64.tar.gz",
            sha256="07389f688d8fe0b77ad754824c09d0be1be19cd4e9f863195d6d545a3c37e988",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-linux_aarch64.tar.gz",
            archive_format="tar.gz",
        ),
        "windows-x64": JavaRuntimeAsset(
            platform_id="windows-x64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-win_x64.zip",
            sha256="ed209ff4293ff581c81d3b4268faf108fbe610e6ed43883de9e5f04308d68a72",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-win_x64.zip",
            archive_format="zip",
        ),
        "windows-arm64": JavaRuntimeAsset(
            platform_id="windows-arm64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-win_aarch64.zip",
            sha256="638c96ff424c380c235f38a9523971040619de08979c7fc27ce6c60c9120430a",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-win_aarch64.zip",
            archive_format="zip",
        ),
        "darwin-x64": JavaRuntimeAsset(
            platform_id="darwin-x64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-macosx_x64.tar.gz",
            sha256="2af1c17d9b2ba530328e52946fe3d4864c0670844918a1dbfb644eb2e2e3e08e",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-macosx_x64.tar.gz",
            archive_format="tar.gz",
        ),
        "darwin-arm64": JavaRuntimeAsset(
            platform_id="darwin-arm64",
            url="https://cdn.azul.com/zulu/bin/zulu17.70.111-ca-jdk17.0.21-macosx_aarch64.tar.gz",
            sha256="8e51495d34f4d5a5b023e2e525c65afb3fb139e40507fcbc3dcf949ca13ce550",  # pragma: allowlist secret
            filename="zulu17.70.111-ca-jdk17.0.21-macosx_aarch64.tar.gz",
            archive_format="tar.gz",
        ),
    }
