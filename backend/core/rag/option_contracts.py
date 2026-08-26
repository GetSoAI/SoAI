"""SoAI - RAG option contracts [backend/core/rag/option_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "VALID_CHUNKING_STRATEGIES",
    "VALID_RETRIEVAL_STRATEGIES",
    "VALID_RETURN_EXTRACT_MODES",
    "build_chunking_strategy_property",
    "build_retrieval_strategy_property",
    "build_return_extract_mode_property",
)

VALID_RETRIEVAL_STRATEGIES: tuple[str, str, str] = ("similarity", "mmr", "hybrid")
VALID_CHUNKING_STRATEGIES: tuple[str, str, str, str] = (
    "token_based",
    "fixed_size",
    "paragraph",
    "semantic",
)
VALID_RETURN_EXTRACT_MODES: tuple[str, str, str] = ("markdown", "text", "html")

_DEFAULT_RETRIEVAL_STRATEGY_DESCRIPTION = "Retrieval strategy: similarity, mmr, or hybrid"
_DEFAULT_CHUNKING_STRATEGY_DESCRIPTION = "Chunking strategy for ingestion."
_DEFAULT_RETURN_EXTRACT_MODE_DESCRIPTION = "Extraction mode for returned content."


def build_retrieval_strategy_property(
    description: str = _DEFAULT_RETRIEVAL_STRATEGY_DESCRIPTION,
) -> JSONDict:
    return {
        "type": "string",
        "description": description,
    }


def build_chunking_strategy_property(
    description: str = _DEFAULT_CHUNKING_STRATEGY_DESCRIPTION,
) -> JSONDict:
    return {
        "type": "string",
        "description": description,
        "enum": list(VALID_CHUNKING_STRATEGIES),
    }


def build_return_extract_mode_property(
    description: str = _DEFAULT_RETURN_EXTRACT_MODE_DESCRIPTION,
) -> JSONDict:
    return {
        "type": "string",
        "description": description,
        "enum": list(VALID_RETURN_EXTRACT_MODES),
    }
