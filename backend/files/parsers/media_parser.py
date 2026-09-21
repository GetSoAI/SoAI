"""SoAI - Base media parser class [backend/files/parsers/media_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.files.protocols import FileParserProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("BaseMediaParser",)


class BaseMediaParser(FileParserProtocol):
    content_separator: str = "\n"

    def _init_media_context(self, file_path: str) -> tuple[JSONDict, list[str]]:
        metadata: JSONDict = {"file_size": os.path.getsize(file_path)}
        return (metadata, [f"File size: {metadata['file_size']} bytes"])
