"""SoAI - Conversation PDF export render task [backend/features/api/routes/webui/conversation_pdf_export_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.browser.html_pdf_renderer import (
    HtmlPdfRenderRequest,
    render_html_file_to_pdf,
    require_pdf_browser_ready,
)
from core.browser.html_pdf_templates import (
    build_pdf_footer_template,
    build_pdf_header_template,
)
from core.browser.pdf_document_merge import merge_pdf_documents
from core.browser.pdf_font_manifest import resolve_pdf_font_cache_root
from core.browser.pdf_font_staging import stage_pdf_fonts
from core.browser.pdf_font_text import extract_pdf_visible_text
from core.errors.exceptions import PayloadTooLargeError
from core.files.content_hashing import hash_file_content
from core.files.locking import async_guarded_file_lock
from core.files.operations import secure_filename
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from core.tasks.progress_reporting import report_progress_without_status_change
from features.api.routes.webui.conversation_pdf_export_snapshot import (
    validate_conversation_pdf_export_snapshot,
)
from features.conversation_export.artifacts import (
    cleanup_conversation_pdf_intermediate_artifacts,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue
    from features.api.routes.webui.conversation_pdf_export_metadata import (
        ConversationPdfExportMetadata,
    )
    from features.api.routes.webui.conversation_pdf_export_staging import (
        ConversationPdfStagedUpload,
    )
    from features.api.runtime.context import ApiContext
    from features.conversation_export.artifacts import ConversationPdfArtifactPaths
    from features.conversation_export.settings import ConversationPdfExportSettings

__all__ = ("render_conversation_pdf_artifact",)

_FILENAME_MAX_STEM_LENGTH = 80


def _resolve_export_filename(title: str) -> str:
    stem = secure_filename(title).strip("._")
    if len(stem) > _FILENAME_MAX_STEM_LENGTH:
        stem = stem[:_FILENAME_MAX_STEM_LENGTH].strip("._")
    if not stem:
        stem = "conversation"
    return f"{stem}.pdf"


async def _read_export_document(path: str) -> str:
    def read_sync() -> str:
        with open_text(path, mode="r", encoding="utf-8", errors="strict") as handle:
            return handle.read()

    return await asyncio.to_thread(read_sync)


async def _merge_and_measure(
    *,
    api_context: ApiContext,
    settings: ConversationPdfExportSettings,
    paths: ConversationPdfArtifactPaths,
    cover_pdf: bytes,
    body_pdf: bytes,
) -> tuple[int, str]:
    estimated_bytes = len(cover_pdf) + len(body_pdf)
    reservation = api_context.dependencies.storage_manager.reserve_disk_space(
        path=paths.task_dir,
        required_bytes=max(estimated_bytes, 1),
        operation="webui.conversation_pdf_export.write_pdf",
        details={"purpose": "conversation_pdf_export_pdf", "size_bytes": estimated_bytes},
    )
    with reservation, claim_reserved_write(reservation, size_bytes=estimated_bytes):
        await asyncio.to_thread(
            merge_pdf_documents,
            cover_pdf=cover_pdf,
            body_pdf=body_pdf,
            output_path=paths.pdf_path,
        )
    measured = await asyncio.to_thread(hash_file_content, paths.pdf_path)
    if measured.size_bytes > settings.max_pdf_bytes:
        raise PayloadTooLargeError("Rendered PDF exceeds the configured maximum size.")
    return measured.size_bytes, measured.sha256_hex


async def render_conversation_pdf_artifact(
    *,
    api_context: ApiContext,
    registry: TaskRegistryProtocol,
    task_id: str,
    settings: ConversationPdfExportSettings,
    paths: ConversationPdfArtifactPaths,
    metadata: ConversationPdfExportMetadata,
    staged: ConversationPdfStagedUpload,
    user_id: int,
) -> dict[str, JSONValue]:
    await report_progress_without_status_change(registry, task_id, 20, status_message="Waiting")
    render_lock_path = os.path.join(settings.temp_dir, "conversation-pdf-render.lock")
    async with async_guarded_file_lock(
        render_lock_path,
        timeout=float(settings.render_timeout_sec + 60),
    ):
        await require_pdf_browser_ready()
        await validate_conversation_pdf_export_snapshot(
            api_context=api_context,
            user_id=user_id,
            metadata=metadata,
        )
        await report_progress_without_status_change(
            registry,
            task_id,
            35,
            status_message="Rendering",
        )
        font_cache_dir = resolve_pdf_font_cache_root()
        body_html = await _read_export_document(staged.html_path)
        cover_html = await _read_export_document(staged.cover_html_path)
        font_text = "\n".join(
            (
                extract_pdf_visible_text(body_html),
                extract_pdf_visible_text(cover_html),
                metadata.title,
                metadata.export_date,
            ),
        )
        await asyncio.to_thread(
            stage_pdf_fonts,
            text=font_text,
            cache_dir=font_cache_dir,
            css_path=paths.font_css_path,
        )
        await report_progress_without_status_change(
            registry,
            task_id,
            40,
            status_message="Rendering cover",
        )
        cover_pdf = await render_html_file_to_pdf(
            HtmlPdfRenderRequest(
                html_path=staged.cover_html_path,
                stylesheet_path=paths.font_css_path,
                asset_root=font_cache_dir,
                header_template="",
                footer_template="",
                timeout_sec=settings.render_timeout_sec,
            ),
            playwright_sessions=api_context.dependencies.playwright_sessions,
        )
        await report_progress_without_status_change(
            registry,
            task_id,
            50,
            status_message="Rendering conversation",
        )
        body_pdf = await render_html_file_to_pdf(
            HtmlPdfRenderRequest(
                html_path=staged.html_path,
                stylesheet_path=paths.font_css_path,
                asset_root=font_cache_dir,
                header_template=build_pdf_header_template(
                    title=metadata.title,
                    logo_data_uri=metadata.small_logo_data_uri,
                ),
                footer_template=build_pdf_footer_template(
                    note_label=metadata.footer_note_label,
                    pages_label=metadata.footer_pages_label,
                    export_date=metadata.export_date,
                ),
                timeout_sec=settings.render_timeout_sec,
            ),
            playwright_sessions=api_context.dependencies.playwright_sessions,
        )
        await report_progress_without_status_change(registry, task_id, 70, status_message="Merging")
        await validate_conversation_pdf_export_snapshot(
            api_context=api_context,
            user_id=user_id,
            metadata=metadata,
        )
        await report_progress_without_status_change(registry, task_id, 85, status_message="Writing")
        pdf_size_bytes, digest = await _merge_and_measure(
            api_context=api_context,
            settings=settings,
            paths=paths,
            cover_pdf=cover_pdf,
            body_pdf=body_pdf,
        )
        cleanup_conversation_pdf_intermediate_artifacts(paths)
        return {
            "download_url": f"/api/v1/webui/conversations/export/pdf/{task_id}/download",
            "filename": _resolve_export_filename(metadata.title),
            "pdf_path": paths.pdf_path,
            "html_size_bytes": staged.html_size_bytes,
            "pdf_size_bytes": pdf_size_bytes,
            "sha256": digest,
        }
