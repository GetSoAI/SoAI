"""SoAI - Actionable unsupported benchmark publication [backend/core/hardware/soaibench_publication_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "SoAIBenchPublicationUnsupportedError",
    "SoAIBenchPublicationCancelledError",
    "SoAIBenchPublicationIncompleteError",
)


class SoAIBenchPublicationUnsupportedError(ValidationError):
    code: str | int = "soaibench_publication_unsupported"
    public_message: str | None = (
        "This GPU does not support this benchmark. No benchmark score is available to publish. Select a supported GPU and complete the benchmark first."
    )


class SoAIBenchPublicationCancelledError(ValidationError):
    code: str | int = "soaibench_publication_cancelled"
    public_message: str | None = (
        "This benchmark was cancelled and has no completed publishable result. Complete a supported benchmark before publication."
    )


class SoAIBenchPublicationIncompleteError(ValidationError):
    code: str | int = "soaibench_publication_incomplete"
    public_message: str | None = (
        "This benchmark has no complete eligible result. Complete a supported certified benchmark before publication."
    )
