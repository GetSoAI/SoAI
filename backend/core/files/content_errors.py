"""SoAI - File content precondition failures [backend/core/files/content_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import PreconditionError

__all__ = ("FileContentChangedError",)


class FileContentChangedError(PreconditionError):
    code: str | int = "file_content_changed"
    public_message: str | None = "The file changed during the operation. Select it again and retry."
