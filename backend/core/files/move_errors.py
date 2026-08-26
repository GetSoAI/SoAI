"""SoAI - File move conflict errors [backend/core/files/move_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("DestinationExistsError",)


class DestinationExistsError(ValidationError): ...
