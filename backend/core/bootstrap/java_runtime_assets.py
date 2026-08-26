"""SoAI - Managed Java runtime asset definitions and catalog [backend/core/bootstrap/java_runtime_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from dataclasses import dataclass

__all__ = (
    "JAVA_RUNTIME_RELEASE",
    "JAVA_RUNTIME_RELEASE_DIR",
    "JavaRuntimeAsset",
    "get_java_runtime_assets",
)

JAVA_RUNTIME_RELEASE = "17.0.19"
JAVA_RUNTIME_RELEASE_DIR = "17.0.19"


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
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-linux-x64.tar.gz",
            sha256=(
                "12769453"
                "6ed818bb"
                "135d2464"
                "ea76fabe"
                "3cfc485c"
                "660a630"
                "4301775e"
                "26a0b7035"
            ),
            filename="microsoft-jdk-17.0.19-linux-x64.tar.gz",
            archive_format="tar.gz",
        ),
        "linux-arm64": JavaRuntimeAsset(
            platform_id="linux-arm64",
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-linux-aarch64.tar.gz",
            sha256=(
                "45248a01"
                "b7ea98ac"
                "568ae801"
                "274a98b3"
                "e581233b"
                "d12b0d54"
                "944598fc"
                "dde37b5f"
            ),
            filename="microsoft-jdk-17.0.19-linux-aarch64.tar.gz",
            archive_format="tar.gz",
        ),
        "windows-x64": JavaRuntimeAsset(
            platform_id="windows-x64",
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-windows-x64.zip",
            sha256=(
                "394d1d82"
                "53d58b46"
                "2300f15f"
                "9c813694"
                "78cf8813"
                "f82dca91"
                "4c3b5dfd"
                "ef080f9f"
            ),
            filename="microsoft-jdk-17.0.19-windows-x64.zip",
            archive_format="zip",
        ),
        "windows-arm64": JavaRuntimeAsset(
            platform_id="windows-arm64",
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-windows-aarch64.zip",
            sha256=(
                "3b00a88f"
                "be2281d7"
                "8f70b28f"
                "0913d3c9"
                "607e7aaf"
                "eea68db5"
                "e7ad2263"
                "d52ddfbd"
            ),
            filename="microsoft-jdk-17.0.19-windows-aarch64.zip",
            archive_format="zip",
        ),
        "darwin-x64": JavaRuntimeAsset(
            platform_id="darwin-x64",
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-macos-x64.tar.gz",
            sha256=(
                "6af364ad"
                "c0c79a5a"
                "8d4ea2ed"
                "c5ecb8cd"
                "7e47360c"
                "2944947c"
                "70482e18"
                "befea046"
            ),
            filename="microsoft-jdk-17.0.19-macos-x64.tar.gz",
            archive_format="tar.gz",
        ),
        "darwin-arm64": JavaRuntimeAsset(
            platform_id="darwin-arm64",
            url="https://aka.ms/download-jdk/microsoft-jdk-17.0.19-macos-aarch64.tar.gz",
            sha256=(
                "5ce59293"
                "b2eb30cb"
                "4e9f0c72"
                "c1ea27ce"
                "a2bfaadc"
                "f0dbbe87"
                "ddd92e03"
                "1c4210be"
            ),
            filename="microsoft-jdk-17.0.19-macos-aarch64.tar.gz",
            archive_format="tar.gz",
        ),
    }
