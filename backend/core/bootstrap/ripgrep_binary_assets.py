"""SoAI - Managed ripgrep asset catalog [backend/core/bootstrap/ripgrep_binary_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
from dataclasses import dataclass

__all__ = (
    "RipgrepAsset",
    "get_ripgrep_assets",
)

RIPGREP_RELEASE = "15.1.0"
RIPGREP_RELEASE_DIR = "15.1.0"


@dataclass(frozen=True, slots=True)
class RipgrepAsset:
    platform_id: str
    url: str
    sha256: str
    filename: str
    archive_format: str


@functools.cache
def get_ripgrep_assets() -> dict[str, RipgrepAsset]:
    base_url = f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_RELEASE}"
    return {
        "linux-x64": RipgrepAsset(
            platform_id="linux-x64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-x86_64-unknown-linux-musl.tar.gz",
            sha256=(
                "1c9297be"
                "4a084eea"
                "7ecaedf9"
                "3eb03d05"
                "8d6faae2"
                "9bbc57ec"
                "daf50639"
                "21491599"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-x86_64-unknown-linux-musl.tar.gz",
            archive_format="tar.gz",
        ),
        "linux-arm64": RipgrepAsset(
            platform_id="linux-arm64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-aarch64-unknown-linux-gnu.tar.gz",
            sha256=(
                "2b661c6e"
                "f508e902"
                "f388e909"
                "8d9c4c5a"
                "ca72c87b"
                "55922d94"
                "abdba830"
                "b4dc885e"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-aarch64-unknown-linux-gnu.tar.gz",
            archive_format="tar.gz",
        ),
        "darwin-x64": RipgrepAsset(
            platform_id="darwin-x64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-x86_64-apple-darwin.tar.gz",
            sha256=(
                "4811cb24"
                "e77cac30"
                "57d6c40b"
                "63ac9bec"
                "f9082eed"
                "d54ca411"
                "b475b755"
                "d3348827"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-x86_64-apple-darwin.tar.gz",
            archive_format="tar.gz",
        ),
        "darwin-arm64": RipgrepAsset(
            platform_id="darwin-arm64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-aarch64-apple-darwin.tar.gz",
            sha256=(
                "378e9732"
                "89176ca0"
                "c6054054"
                "ee7f631a"
                "065874a3"
                "52bf43f0"
                "fa60ef07"
                "9b6ba715"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-aarch64-apple-darwin.tar.gz",
            archive_format="tar.gz",
        ),
        "windows-x64": RipgrepAsset(
            platform_id="windows-x64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-x86_64-pc-windows-msvc.zip",
            sha256=(
                "124510b9"
                "4b6baa33"
                "80d051fd"
                "f4650eaa"
                "80a302c8"
                "76d611e9"
                "dba0b2e1"
                "8d87493a"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-x86_64-pc-windows-msvc.zip",
            archive_format="zip",
        ),
        "windows-arm64": RipgrepAsset(
            platform_id="windows-arm64",
            url=f"{base_url}/ripgrep-{RIPGREP_RELEASE}-aarch64-pc-windows-msvc.zip",
            sha256=(
                "00d931fb"
                "5237c969"
                "6ca49308"
                "818edb76"
                "d8eb6fc1"
                "32761cb2"
                "a1bd616b"
                "2df02f8e"
            ),
            filename=f"ripgrep-{RIPGREP_RELEASE}-aarch64-pc-windows-msvc.zip",
            archive_format="zip",
        ),
    }
