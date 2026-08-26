"""SoAI - File explorer runtime settings resolution [backend/features/file_explorer/runtime_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.clamped_numeric import read_config_int_min_clamped
from core.config.protocols import ConfigProtocol
from core.files.protocols import FilesPathResolverProtocol
from core.files.upload_policy import resolve_temp_directory_path

__all__ = (
    "FileExplorerRuntimeSettings",
    "resolve_file_explorer_runtime_settings",
)


@dataclass(frozen=True, slots=True)
class FileExplorerRuntimeSettings:
    allow_symlinks: bool
    text_preview_limit_bytes: int
    listing_pagination_limit: int
    maximum_download_archive_bytes: int
    maximum_download_archive_members: int
    temp_dir: str
    database_path: str | None


def resolve_file_explorer_runtime_settings(
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
) -> FileExplorerRuntimeSettings:
    text_limit_kb = config.get_int("DATA.FILE_EXPLORER.TEXT_PREVIEW_LIMIT_KB")
    if text_limit_kb <= 0:
        text_limit_kb = 512
    listing_limit = config.get_int("DATA.FILE_EXPLORER.LISTING_PAGINATION_LIMIT")
    if listing_limit <= 0:
        listing_limit = 200
    database_path_value = config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
    return FileExplorerRuntimeSettings(
        allow_symlinks=config.get_bool("DATA.FILE_EXPLORER.ALLOW_SYMLINKS"),
        text_preview_limit_bytes=text_limit_kb * 1024,
        listing_pagination_limit=min(int(listing_limit), 1000),
        maximum_download_archive_bytes=require_config_mib_to_bytes(
            config.get("DATA.FILE_EXPLORER.MAX_DOWNLOAD_ARCHIVE_SIZE_MB", 4096),
            field="DATA.FILE_EXPLORER.MAX_DOWNLOAD_ARCHIVE_SIZE_MB",
        ),
        maximum_download_archive_members=read_config_int_min_clamped(
            config,
            "DATA.FILE_EXPLORER.MAX_DOWNLOAD_ARCHIVE_MEMBERS",
            100000,
            minimum=1,
        ),
        temp_dir=resolve_temp_directory_path(
            config,
            files,
            error_message="SYSTEM.PATHS.TEMP is required for file explorer temp directory configuration.",
        ),
        database_path=files.resolve_path(database_path_value) if database_path_value else None,
    )
