"""SoAI - Asynchronous ZIP and TAR document archive parser [backend/files/parsers/archive_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import zipfile
from tarfile import TarError
from typing import TYPE_CHECKING, override

from core.archives.tar_extraction import async_safe_tar_extractall
from core.archives.zip_extraction import async_safe_zip_extractall
from core.errors.exceptions import ValidationError
from core.files.document_type_detection import extract_extension
from core.files.extensions.archives import TAR_EXTENSIONS, ZIP_EXTENSIONS
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.protocols import FileParserProtocol
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.types import ParsedDocument, ParseExecutionContext
from files.parsers.archive_content_parser import parse_extracted_archive_contents

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("ArchiveParser",)


class ArchiveParser(FileParserProtocol):
    content_separator = "\n\n---\n\n"

    def __init__(
        self,
        parsers_registry: dict[str, FileParserProtocol],
        storage_manager: StorageManagerProtocol,
    ) -> None:
        self._parsers = parsers_registry
        self._storage_manager = storage_manager

    @override
    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        extension = extract_extension(context.display_name or context.source_path)
        if extension not in TAR_EXTENSIONS | ZIP_EXTENSIONS:
            raise ValidationError("Unsupported document archive format.")
        async with scoped_temp_directory(
            directory=None,
            prefix="soai-document-archive-",
            operation_label="document-archive",
        ) as temp_dir:
            raise_if_parse_cancelled(context)
            await self._extract(context.source_path, temp_dir, extension)
            raise_if_parse_cancelled(context)
            result = await parse_extracted_archive_contents(
                temp_dir,
                self._parsers,
                _nested_archive_extensions(),
                "ZIP" if extension in ZIP_EXTENSIONS else "TAR",
                parent_context=context,
            )
            return ParsedDocument(
                content=self.content_separator.join(result.content_parts),
                metadata={"archive_type": extension},
                extraction_state=result.extraction_state,
                warnings=result.warnings,
            )

    async def _extract(self, source_path: str, temp_dir: str, extension: str) -> None:
        try:
            if extension in ZIP_EXTENSIONS:
                await async_safe_zip_extractall(
                    source_path,
                    temp_dir,
                    reservation_provider=self._storage_manager,
                )
                return
            await async_safe_tar_extractall(
                source_path,
                temp_dir,
                reservation_provider=self._storage_manager,
            )
        except (zipfile.BadZipFile, TarError) as exception:
            raise ValidationError("Document archive is invalid or corrupt.") from exception


def _nested_archive_extensions() -> frozenset[str]:
    return TAR_EXTENSIONS | ZIP_EXTENSIONS | frozenset({"rar"})
