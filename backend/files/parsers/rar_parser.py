"""SoAI - RAR archive parser [backend/files/parsers/rar_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from types import ModuleType
from typing import ClassVar, override

from core.archives.rar_extraction import safe_rar_extract_members
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import StateError, ValidationError
from core.files.extensions.archives import TAR_EXTENSIONS, ZIP_EXTENSIONS
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.protocols import FileParserProtocol, RarFileProtocol
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.types import ParsedDocument, ParseExecutionContext
from core.hardware.protocols_storage import StorageManagerProtocol
from core.imports.availability import module_available, require_module
from files.parsers.archive_content_parser import parse_extracted_archive_contents

__all__ = ("RARParser",)


class _UnavailableRarfileError(Exception): ...


class _RarfileRuntime:
    module: ClassVar[ModuleType | None] = None


if module_available("rarfile"):
    import rarfile

    _RarfileRuntime.module = rarfile


class RARParser(FileParserProtocol):
    content_separator: str = "\n\n---\n\n"

    def __init__(
        self,
        parsers_registry: dict[str, FileParserProtocol],
        storage_manager: StorageManagerProtocol,
    ) -> None:
        self._parsers = parsers_registry
        self._storage_manager = storage_manager

    @override
    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        require_module("rarfile", feature="RAR archive parsing")
        async with scoped_temp_directory(
            directory=None,
            prefix="soai-rar-archive-",
            operation_label="rar-archive",
        ) as temp_dir:
            raise_if_parse_cancelled(context)
            await run_joined_thread_call(
                self._extract_archive_sync,
                context.source_path,
                temp_dir,
                task_name="rar-archive-extraction",
            )
            parsed_contents = await parse_extracted_archive_contents(
                temp_dir,
                self._parsers,
                TAR_EXTENSIONS | ZIP_EXTENSIONS | frozenset({"rar"}),
                "RAR",
                parent_context=context,
            )
        return ParsedDocument(
            content=self.content_separator.join(parsed_contents.content_parts),
            metadata={"archive_type": "rar"},
            extraction_state=parsed_contents.extraction_state,
            warnings=parsed_contents.warnings,
        )

    def _extract_archive_sync(self, file_path: str, temp_dir: str) -> None:
        need_first_volume_error, bad_rar_file_error, rar_cannot_exec_error = (
            self._resolve_rarfile_errors()
        )
        try:
            archive = self._open_rarfile_archive(file_path)
            try:
                safe_rar_extract_members(
                    archive,
                    temp_dir,
                    reservation_provider=self._storage_manager,
                )
            finally:
                archive.close()
        except tuple(
            {need_first_volume_error, bad_rar_file_error, rar_cannot_exec_error},
        ) as exception:
            if isinstance(exception, need_first_volume_error):
                raise ValidationError(
                    "RAR multi-volume archive - first volume required",
                ) from exception
            if isinstance(exception, bad_rar_file_error):
                raise ValidationError("Invalid or corrupted RAR file") from exception
            if isinstance(exception, rar_cannot_exec_error):
                raise StateError(
                    "RAR extraction tool (unrar) not installed on system",
                ) from exception
            raise

    def _open_rarfile_archive(self, file_path: str) -> RarFileProtocol:
        rarfile_module = _RarfileRuntime.module
        if rarfile_module is None:
            raise StateError("RAR archive parsing requires the 'rarfile' dependency.")
        try:
            rarfile_archive_ctor = rarfile_module.RarFile
        except AttributeError:
            rarfile_archive_ctor = None
        if not callable(rarfile_archive_ctor):
            raise StateError(
                "RAR archive parsing is unavailable because rarfile.RarFile is unavailable.",
            )
        archive = rarfile_archive_ctor(file_path, mode="r")
        if not isinstance(archive, RarFileProtocol):
            raise StateError(
                "RAR archive parsing is unavailable because rarfile.RarFile does not satisfy the RAR archive protocol.",
            )
        return archive

    def _resolve_rarfile_errors(
        self,
    ) -> tuple[type[Exception], type[Exception], type[Exception]]:
        rarfile_module = _RarfileRuntime.module
        if rarfile_module is None:
            return (
                _UnavailableRarfileError,
                _UnavailableRarfileError,
                _UnavailableRarfileError,
            )
        try:
            need_first_volume_error = rarfile_module.NeedFirstVolume
        except AttributeError:
            need_first_volume_error = None
        try:
            bad_rar_file_error = rarfile_module.BadRarFile
        except AttributeError:
            bad_rar_file_error = None
        try:
            rar_cannot_exec_error = rarfile_module.RarCannotExec
        except AttributeError:
            rar_cannot_exec_error = None
        if not isinstance(need_first_volume_error, type) or not issubclass(
            need_first_volume_error,
            Exception,
        ):
            need_first_volume_error = _UnavailableRarfileError
        if not isinstance(bad_rar_file_error, type) or not issubclass(
            bad_rar_file_error,
            Exception,
        ):
            bad_rar_file_error = _UnavailableRarfileError
        if not isinstance(rar_cannot_exec_error, type) or not issubclass(
            rar_cannot_exec_error,
            Exception,
        ):
            rar_cannot_exec_error = _UnavailableRarfileError
        return need_first_volume_error, bad_rar_file_error, rar_cannot_exec_error
