"""SoAI - Binary diagnostic/profiling extension constants [backend/core/files/extensions/binaries_extensions_diagnostics_and_profiling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

BINARY_EXTENSIONS_DIAGNOSTICS_AND_PROFILING = frozenset(
    (
        "coredump",
        "crashlog",
        "dmp",
        "etl",
        "evt",
        "evtx",
        "gcda",
        "gcno",
        "hdmp",
        "hprof",
        "mdmp",
        "profraw",
        "trace",
    ),
)
