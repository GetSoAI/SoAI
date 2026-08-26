"""SoAI - Conversation PDF export artifact retention [backend/features/conversation_export/retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.timing.epoch import epoch_seconds_float
from features.conversation_export.artifacts import (
    CONVERSATION_PDF_EXPORT_MARKER_NAME,
    cleanup_conversation_pdf_task_directory,
)

__all__ = ("sweep_conversation_pdf_export_artifacts",)


def _is_expired_task_directory(task_dir: str, *, retention_sec: int, now_sec: float) -> bool:
    if not os.path.isfile(os.path.join(task_dir, CONVERSATION_PDF_EXPORT_MARKER_NAME)):
        return False
    return now_sec - os.path.getmtime(task_dir) > retention_sec


def sweep_conversation_pdf_export_artifacts(*, temp_dir: str, retention_sec: int) -> int:
    if not os.path.isdir(temp_dir):
        return 0
    now_sec = epoch_seconds_float()
    removed = 0
    for entry_name in os.listdir(temp_dir):
        task_dir = os.path.join(temp_dir, entry_name)
        if not os.path.isdir(task_dir):
            continue
        if not _is_expired_task_directory(
            task_dir,
            retention_sec=retention_sec,
            now_sec=now_sec,
        ):
            continue
        cleanup_conversation_pdf_task_directory(task_dir)
        if not os.path.isdir(task_dir):
            removed += 1
    return removed
