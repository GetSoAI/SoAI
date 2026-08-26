"""SoAI - Storage mutation phase contracts [backend/core/os/storage_mutation_phases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "STORAGE_FORMAT_PHASES",
    "STORAGE_FORMAT_RECOVERABLE_PHASES",
)

STORAGE_FORMAT_RECOVERABLE_PHASES = ("accepted", "format_prepared", "format_wiped")
STORAGE_FORMAT_PHASES = ("accepted", "format_prepared", "format_wiped", "complete")
