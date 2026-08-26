"""SoAI - Plugin SDK quantization token extraction helpers [backend/plugin_sdk/contracts/quantization_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from collections.abc import Sequence

__all__ = ("extract_quantization_token",)


def extract_quantization_token(
    value: str | None,
    pattern_texts: Sequence[str],
    *,
    filename_suffixes: frozenset[str] = frozenset(),
) -> str | None:
    if not isinstance(value, str):
        return None
    token_source = value.strip().lower()
    if filename_suffixes:
        candidate = os.path.basename(token_source)
        stem, suffix = os.path.splitext(candidate)
        token_source = stem if suffix in filename_suffixes else candidate
    for pattern_text in pattern_texts:
        matches = list(re.finditer(pattern_text, token_source))
        if matches:
            return matches[-1].group(1)
    return None
