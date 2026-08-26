"""SoAI - Upload validation error contracts [backend/core/files/upload_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("MissingRequiredUploadMetadataError",)


class MissingRequiredUploadMetadataError(ValidationError): ...
