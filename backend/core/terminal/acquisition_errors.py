"""SoAI - Safe PTY acquisition ownership errors [backend/core/terminal/acquisition_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("PTYAcquisitionError",)


class PTYAcquisitionError(ValidationError):
    code: str | int = "terminal_release_unconfirmed"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.public_message = message
