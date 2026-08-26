"""SoAI - Archive and container file extension constants [backend/core/files/extensions/archives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

TAR_EXTENSIONS = frozenset(("tar", "tgz", "tbz2", "txz"))
ZIP_EXTENSIONS = frozenset(("zip", "soaiplugin"))
ISO_EXTENSIONS = frozenset(("iso", "udf"))
COMPRESSED_EXTENSIONS = frozenset(("gz", "gzip", "bz2", "xz", "lzma", "zst", "zstd"))
