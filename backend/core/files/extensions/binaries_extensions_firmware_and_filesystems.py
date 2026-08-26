"""SoAI - Binary firmware/filesystem extension constants [backend/core/files/extensions/binaries_extensions_firmware_and_filesystems.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

BINARY_EXTENSIONS_FIRMWARE_AND_FILESYSTEMS = frozenset(
    (
        "blk",
        "bio",
        "cap",
        "cramfs",
        "eep",
        "erf",
        "fw",
        "hex",
        "ips",
        "ipsw",
        "jffs2",
        "s19",
        "shsh",
        "squashfs",
        "srec",
        "sst",
        "ubifs",
        "uf2",
        "vxd",
        "wlt",
        "yaffs2",
    ),
)
