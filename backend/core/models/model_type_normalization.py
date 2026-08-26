"""SoAI - Model type token normalization [backend/core/models/model_type_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

__all__ = ("normalize_model_type_tokens",)


def normalize_model_type_tokens(model_types: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in model_types:
        token = item.strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)
