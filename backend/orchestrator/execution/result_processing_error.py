"""SoAI - Internal result-processing failure marker [backend/orchestrator/execution/result_processing_error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("ResultProcessingError",)


class ResultProcessingError(StateError): ...
