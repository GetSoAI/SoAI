"""SoAI - Web fetch extraction outcome projection [backend/mcp/rag/scraper/extraction_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.mcp.protocols_rag import FetchedContentProtocol
    from core.types.json import JSONDict

__all__ = ("fetched_extraction_fields",)


def fetched_extraction_fields(fetched: FetchedContentProtocol) -> JSONDict:
    fields: JSONDict = {"extraction_state": fetched.extraction_state.value}
    if fetched.warnings:
        fields["extraction_warnings"] = list(fetched.warnings)
    if fetched.missing_capabilities:
        fields["missing_capabilities"] = list(fetched.missing_capabilities)
    return fields
