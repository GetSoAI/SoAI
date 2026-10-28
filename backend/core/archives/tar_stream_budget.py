"""SoAI - TAR parser metadata resource enforcement [backend/core/archives/tar_stream_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from collections.abc import Callable
from tarfile import (
    GNUTYPE_LONGLINK,
    GNUTYPE_LONGNAME,
    GNUTYPE_SPARSE,
    SOLARIS_XHDTYPE,
    XGLTYPE,
    XHDTYPE,
    TarFile,
    TarInfo,
)
from typing import TYPE_CHECKING, Literal, NoReturn, override

from core.archives.resource_limits import ArchivePlanningBudget, default_archive_resource_limits
from core.errors.exceptions import ValidationError
from core.files.staged_transfer import STAGED_TRANSFER_CHUNK_SIZE, iter_reader_chunks
from core.filesystem.open_files import open_binary

__all__ = ("ResourceLimitedTarFile", "ResourceLimitedTarInfo")

TAR_EXTENSION_TYPES = frozenset(
    {
        GNUTYPE_LONGNAME,
        GNUTYPE_LONGLINK,
        XHDTYPE,
        XGLTYPE,
        SOLARIS_XHDTYPE,
    }
)
SPARSE_REJECTION_MESSAGE = "GNU sparse TAR members are not supported."


class ResourceLimitedTarInfo(TarInfo):
    if TYPE_CHECKING:

        def _proc_builtin(self, tarfile: TarFile) -> TarInfo: ...

        def _proc_gnulong(self, tarfile: TarFile) -> TarInfo: ...

        def _proc_pax(self, tarfile: TarFile) -> TarInfo: ...

    def _proc_member(self, tarfile: TarFile) -> TarInfo:
        if not isinstance(tarfile, ResourceLimitedTarFile):
            raise ValidationError("Resource-limited TAR metadata parser is misconfigured.")
        if self.type == GNUTYPE_SPARSE:
            raise ValidationError(SPARSE_REJECTION_MESSAGE)
        if self.type in TAR_EXTENSION_TYPES:
            tarfile.add_extension_header(self)
        if self.type in {GNUTYPE_LONGNAME, GNUTYPE_LONGLINK}:
            return self._proc_gnulong(tarfile)
        if self.type in {XHDTYPE, XGLTYPE, SOLARIS_XHDTYPE}:
            return self._proc_pax(tarfile)
        return self._proc_builtin(tarfile)

    def _proc_gnusparse_00(
        self,
        *_sparse_arguments: TarInfo | list[tuple[int, bytes, bytes]],
    ) -> NoReturn:
        raise ValidationError(SPARSE_REJECTION_MESSAGE)

    def _proc_gnusparse_01(
        self,
        *_sparse_arguments: TarInfo | dict[str, str],
    ) -> NoReturn:
        raise ValidationError(SPARSE_REJECTION_MESSAGE)

    def _proc_gnusparse_10(
        self,
        *_sparse_arguments: TarInfo | dict[str, str] | TarFile,
    ) -> NoReturn:
        raise ValidationError(SPARSE_REJECTION_MESSAGE)


class ResourceLimitedTarFile(TarFile):
    def __init__(
        self,
        name: str | None = None,
        mode: Literal["r", "a", "w", "x"] = "r",
        fileobj: io.BufferedIOBase | io.RawIOBase | None = None,
        tarinfo: type[TarInfo] | None = None,
    ) -> None:
        if tarinfo is not None and tarinfo is not ResourceLimitedTarInfo:
            raise ValidationError(
                "Resource-limited TAR parsing requires its protected member type."
            )
        self.planning_budget = ArchivePlanningBudget(default_archive_resource_limits())
        self.firstmember: TarInfo | None = None
        self.progress_check: Callable[[], None] | None = None
        super().__init__(
            name=name,
            mode=mode,
            fileobj=fileobj,
            tarinfo=tarinfo or ResourceLimitedTarInfo,
        )

    def add_extension_header(self, member: TarInfo) -> None:
        self.planning_budget.add_member(
            metadata_bytes=member.size,
            name=member.name or "<TAR extension header>",
        )

    @override
    def next(self) -> TarInfo | None:
        progress_check = self.progress_check
        if progress_check is not None:
            while self.firstmember is None and self.offset > self.fileobj.tell():
                progress_check()
                remaining = self.offset - self.fileobj.tell()
                if not self.fileobj.read(min(remaining, STAGED_TRANSFER_CHUNK_SIZE)):
                    break
            progress_check()
        return super().next()

    @override
    def makefile(
        self, tarinfo: TarInfo, targetpath: str | bytes | os.PathLike[str] | os.PathLike[bytes]
    ) -> None:
        progress_check = self.progress_check
        if progress_check is None:
            super().makefile(tarinfo, targetpath)
            return
        self._extract_regular_file(tarinfo, os.fsdecode(targetpath), progress_check)

    def _extract_regular_file(
        self, tarinfo: TarInfo, targetpath: str, progress_check: Callable[[], None]
    ) -> None:
        progress_check()
        source = self.extractfile(tarinfo)
        if source is None:
            raise ValidationError("Validated TAR file has no readable content.")
        received = 0
        with source, open_binary(targetpath, mode="wb") as destination:
            for chunk in iter_reader_chunks(source.read):
                progress_check()
                received += len(chunk)
                if received > tarinfo.size:
                    raise ValidationError("TAR file exceeds its declared size.")
                destination.write(chunk)
        if received != tarinfo.size:
            raise ValidationError("TAR file ended before its declared size.")
