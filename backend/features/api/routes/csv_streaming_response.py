"""SoAI - Shared CSV streaming responses [backend/features/api/routes/csv_streaming_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from core.files.export import build_content_disposition_attachment

__all__ = ("build_csv_export_stream_response",)


def build_csv_export_stream_response(
    *,
    filename: str,
    csv_bytes: AsyncIterator[bytes],
) -> StreamingResponse:
    headers = {
        "Content-Disposition": build_content_disposition_attachment(filename),
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )
