"""SoAI - Backup completion summary logging [backend/app/backup/backup_completion_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.size_format import format_size
from core.logging.protocols import LoggerProtocol

__all__ = ("log_backup_completion_summary",)


def log_backup_completion_summary(
    *,
    logger: LoggerProtocol,
    backup_id: str,
    elapsed_seconds: float,
    total_size_bytes: int,
    file_count: int,
    backed_up_targets: dict[str, list[tuple[str, int]]],
) -> None:
    if not backed_up_targets:
        logger.info(
            "Backup '%s' completed in %.1fs. Total size: %s, Files: %s (no target summary available)",
            backup_id,
            elapsed_seconds,
            format_size(total_size_bytes),
            file_count,
        )
        return
    target_summaries: list[str] = []
    for target_name, files in backed_up_targets.items():
        target_size = sum(file_entry[1] for file_entry in files)
        if len(files) == 1:
            target_summaries.append(f"{target_name}: {files[0][0]} ({format_size(target_size)})")
            continue
        file_names = ", ".join(file_entry[0] for file_entry in files)
        target_summaries.append(
            f"{target_name}: {len(files)} files ({format_size(target_size)}) [{file_names}]",
        )
    targets_str = " | ".join(target_summaries)
    logger.info(
        "Backup '%s' completed in %.1fs. Total size: %s, Files: %s. Targets: %s",
        backup_id,
        elapsed_seconds,
        format_size(total_size_bytes),
        file_count,
        targets_str,
    )
