"""SoAI - Storage services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/storage/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.files.protocols import (
        DocumentReaderProtocol,
        FileExplorerBatchProtocol,
        FileExplorerCoreProtocol,
        FileExplorerDownloadProtocol,
        FileExplorerListingProtocol,
        FileExplorerSearchProtocol,
        FileExplorerTaskLauncherProtocol,
        FileParserRegistryFactoryProtocol,
    )
    from features.api.runtime.internal_protocols import BackupServiceProtocol

__all__ = ("StorageServicesProtocol",)


class StorageServicesProtocol(Protocol):
    @property
    def backup_service(self) -> BackupServiceProtocol: ...

    @property
    def document_reader(self) -> DocumentReaderProtocol: ...

    @property
    def parser_registry_factory(self) -> FileParserRegistryFactoryProtocol: ...

    @property
    def file_explorer_core(self) -> FileExplorerCoreProtocol | None: ...

    @property
    def file_explorer_batch(self) -> FileExplorerBatchProtocol | None: ...

    @property
    def file_explorer_tasks(self) -> FileExplorerTaskLauncherProtocol | None: ...

    @property
    def file_explorer_search(self) -> FileExplorerSearchProtocol | None: ...

    @property
    def file_explorer_download(self) -> FileExplorerDownloadProtocol | None: ...

    @property
    def file_explorer_listings(self) -> FileExplorerListingProtocol | None: ...
