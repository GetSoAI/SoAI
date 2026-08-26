"""SoAI - File catalog methods for DatabaseFiles [backend/database/repositories/files/service_file_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.database_types import (
    FileCatalogListPage,
    FileCatalogReconciliationRecord,
    FileCatalogRecord,
    FileCatalogRecordWithPath,
)
from core.openai.file_list_limits import OPENAI_FILE_LIST_DEFAULT_LIMIT
from database.repositories.files.catalog import (
    get_all_file_records_for_reconciliation_query,
    get_file_info_query,
    get_file_info_with_path_query,
    sync_add_file,
    sync_delete_file,
    sync_delete_files_by_ids,
)
from database.repositories.files.catalog_listing import list_files_query
from database.repositories.files.internal_protocols import DatabaseFilesCatalogProtocol

__all__ = (
    "add_file",
    "delete_file",
    "delete_files_by_ids",
    "get_all_file_records_for_reconciliation",
    "get_file_info",
    "get_file_info_with_path",
    "list_files",
)


async def add_file(
    self: DatabaseFilesCatalogProtocol,
    file_id: str,
    filename: str,
    purpose: str,
    size_bytes: int,
    content_sha256: str,
    created_at_ms: int,
    file_path: str,
    user_id: int | None,
    api_key_id: str | None,
    status: str,
    status_details: str | None,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_add_file,
        file_id,
        filename,
        purpose,
        size_bytes,
        content_sha256,
        created_at_ms,
        file_path,
        user_id,
        api_key_id,
        status,
        status_details,
    )


async def get_file_info(
    self: DatabaseFilesCatalogProtocol,
    file_id: str,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> FileCatalogRecord | None:
    return await self.core.reader.execute_read(
        get_file_info_query,
        file_id,
        enforce_owner=enforce_owner,
        user_id=user_id,
        api_key_id=api_key_id,
    )


async def get_file_info_with_path(
    self: DatabaseFilesCatalogProtocol,
    file_id: str,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> FileCatalogRecordWithPath | None:
    return await self.core.reader.execute_read(
        get_file_info_with_path_query,
        file_id,
        enforce_owner=enforce_owner,
        user_id=user_id,
        api_key_id=api_key_id,
    )


async def list_files(
    self: DatabaseFilesCatalogProtocol,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
    purpose: str | None = None,
    after: str | None = None,
    limit: int = OPENAI_FILE_LIST_DEFAULT_LIMIT,
    order: str = "desc",
) -> FileCatalogListPage:
    return await self.core.reader.execute_read(
        list_files_query,
        enforce_owner=enforce_owner,
        user_id=user_id,
        api_key_id=api_key_id,
        purpose=purpose,
        after=after,
        limit=limit,
        order=order,
    )


async def delete_file(
    self: DatabaseFilesCatalogProtocol,
    file_id: str,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_delete_file,
        file_id,
        enforce_owner,
        user_id,
        api_key_id,
    )


async def get_all_file_records_for_reconciliation(
    self: DatabaseFilesCatalogProtocol,
) -> list[FileCatalogReconciliationRecord]:
    return await self.core.reader.execute_read(get_all_file_records_for_reconciliation_query)


async def delete_files_by_ids(self: DatabaseFilesCatalogProtocol, file_ids: list[str]) -> int:
    return await self.core.writer.queue_write_operation(
        sync_delete_files_by_ids,
        file_ids,
    )
