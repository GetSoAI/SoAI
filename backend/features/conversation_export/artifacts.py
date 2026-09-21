"""SoAI - Conversation PDF export artifact paths [backend/features/conversation_export/artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SecurityError, ValidationError
from core.files.operations import secure_filename
from core.files.path_policy import is_path_inside_directory, is_same_path
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "CONVERSATION_PDF_EXPORT_MARKER_NAME",
    "ConversationPdfArtifactPaths",
    "build_conversation_pdf_artifact_paths",
    "cleanup_conversation_pdf_intermediate_artifacts",
    "cleanup_conversation_pdf_task_directory",
    "require_export_artifact_path",
    "write_conversation_pdf_task_marker",
)

LOGGER_NAME = "SoAI.features.conversation_export.artifacts"
OPERATION_CONVERSATION_PDF_EXPORT_CLEANUP = "webui.conversation_pdf_export.cleanup"
CONVERSATION_PDF_EXPORT_MARKER_NAME = ".soai-conversation-pdf-export"


@dataclass(frozen=True, slots=True)
class ConversationPdfArtifactPaths:
    task_dir: str
    upload_path: str
    cover_html_path: str
    font_css_path: str
    pdf_path: str


def build_conversation_pdf_artifact_paths(
    temp_dir: str,
    task_id: str,
) -> ConversationPdfArtifactPaths:
    safe_task_id = secure_filename(task_id)
    if not safe_task_id:
        raise ValidationError("PDF export task id is invalid.")
    task_dir = os.path.abspath(os.path.join(temp_dir, safe_task_id))
    return ConversationPdfArtifactPaths(
        task_dir=task_dir,
        upload_path=os.path.join(task_dir, "upload.html"),
        cover_html_path=os.path.join(task_dir, "cover.html"),
        font_css_path=os.path.join(task_dir, "pdf-fonts.css"),
        pdf_path=os.path.join(task_dir, "conversation.pdf"),
    )


def require_export_artifact_path(temp_dir: str, pdf_path: str) -> str:
    root = os.path.realpath(temp_dir)
    candidate = os.path.realpath(pdf_path)
    if is_same_path(root, candidate) or not is_path_inside_directory(root, candidate):
        raise SecurityError("PDF export artifact path is outside the export directory.")
    if not os.path.isfile(candidate):
        raise ValidationError("PDF export artifact is missing.")
    return candidate


def _log_cleanup_failure(
    exception: OSError,
    message: str,
    details: Mapping[str, JSONValue],
) -> None:
    log_handled_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=message,
        operation=OPERATION_CONVERSATION_PDF_EXPORT_CLEANUP,
        details=details,
        level="warning",
    )


def cleanup_conversation_pdf_task_directory(task_dir: str) -> None:
    if not task_dir or not os.path.isdir(task_dir):
        return
    marker_path = os.path.join(task_dir, CONVERSATION_PDF_EXPORT_MARKER_NAME)
    if not os.path.isfile(marker_path):
        return
    try:
        shutil.rmtree(task_dir)
    except OSError as exception:
        _log_cleanup_failure(
            exception,
            "Failed to remove conversation PDF export task directory.",
            {"task_dir": task_dir},
        )


def cleanup_conversation_pdf_intermediate_artifacts(paths: ConversationPdfArtifactPaths) -> None:
    for path in (paths.upload_path, paths.cover_html_path, paths.font_css_path):
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        except OSError as exception:
            _log_cleanup_failure(
                exception,
                "Failed to remove a conversation PDF export intermediate artifact.",
                {"artifact_path": path},
            )


def write_conversation_pdf_task_marker(task_dir: str) -> None:
    os.makedirs(task_dir, exist_ok=True)
    marker_path = os.path.join(task_dir, CONVERSATION_PDF_EXPORT_MARKER_NAME)
    with open_text(marker_path, mode="w", encoding="utf-8", errors="strict") as handle:
        handle.write(str(epoch_ms()))
