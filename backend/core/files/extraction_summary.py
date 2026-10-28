"""SoAI - Persisted document extraction summary [backend/core/files/extraction_summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "EXTRACTION_SUMMARY_METADATA_KEY",
    "build_extraction_summary",
    "read_missing_capabilities",
)

EXTRACTION_SUMMARY_METADATA_KEY = "extraction_summary"
_MISSING_CAPABILITIES_KEY = "missing_capabilities"


def build_extraction_summary(missing_capabilities: tuple[str, ...]) -> JSONDict:
    if not missing_capabilities:
        return {}
    return {_MISSING_CAPABILITIES_KEY: sorted(set(missing_capabilities))}


def read_missing_capabilities(metadata: JSONValue) -> tuple[str, ...]:
    if not isinstance(metadata, dict):
        return ()
    summary = metadata.get(EXTRACTION_SUMMARY_METADATA_KEY)
    if not isinstance(summary, dict):
        return ()
    values = summary.get(_MISSING_CAPABILITIES_KEY)
    if not isinstance(values, list):
        return ()
    return tuple(sorted({value for value in values if isinstance(value, str) and value}))
