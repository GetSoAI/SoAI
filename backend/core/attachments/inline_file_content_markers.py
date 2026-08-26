"""SoAI - Inline attachment file-content markers [backend/core/attachments/inline_file_content_markers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "INLINE_FILE_CONTENT_BEGIN_MARKER",
    "INLINE_FILE_CONTENT_END_MARKER",
    "INLINE_FILE_CONTENT_TRUNCATED_MARKER",
)

INLINE_FILE_CONTENT_BEGIN_MARKER = "[BEGIN UNTRUSTED FILE CONTENT]"
INLINE_FILE_CONTENT_END_MARKER = "[END UNTRUSTED FILE CONTENT]"
INLINE_FILE_CONTENT_TRUNCATED_MARKER = "[FILE CONTENT TRUNCATED]"
