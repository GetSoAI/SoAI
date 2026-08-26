"""SoAI - Hardware device display-name boilerplate stripping [backend/core/hardware/device_display_name.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_device_display_name",)

TRADEMARK_SYMBOL_PATTERN_TEXT = r"[®™©]"
TRADEMARK_MARKER_PATTERN_TEXT = r"\((?:R|TM|C)\)"
AMD_ENTITY_PATTERN_TEXT = r"\bAdvanced Micro Devices\b,?(?:\s*Inc\.?)?(?:\s*\[AMD(?:/ATI)?\])?"
NVIDIA_ENTITY_PATTERN_TEXT = r"\bNVIDIA Corporation\b"
INTEL_ENTITY_PATTERN_TEXT = r"\bIntel Corporation\b"
BASE_CLOCK_SUFFIX_PATTERN_TEXT = r"\s*(?:\bCPU\b\s*)?@\s*[\d.]+\s*[MG]Hz\s*$"
MODEL_NUMBER_FILLER_PATTERN_TEXT = r"\b(?:CPU|Processor)\s+(?=\S*\d)"
COMPUTE_CORES_SUFFIX_PATTERN_TEXT = r",\s*\d+\s+Compute Cores\s+\d+C\+\d+G\s*$"
NUMERIC_CORE_SUFFIX_PATTERN_TEXT = r"\s*\b\d+-Cores?(?:\s+Processor)?\s*$"
WORD_CORE_SUFFIX_PATTERN_TEXT = (
    r"\s*\b(?:Sixty-Four|Forty-Eight|Thirty-Two|Twenty-Four|Twenty|Sixteen|Twelve|Ten"
    r"|Eight|Six|Quad|Four|Three|Dual|Two)-Cores?(?:\s+Processor)?\s*$"
)
TRAILING_PROCESSOR_PATTERN_TEXT = r"\s*\bProcessor\s*$"
SPACE_BEFORE_SEPARATOR_PATTERN_TEXT = r"\s+([,;])"
COLLAPSIBLE_WHITESPACE_PATTERN_TEXT = r"\s+"
SURROUNDING_SEPARATORS = " ,;:"

DISPLAY_NAME_RULES: tuple[tuple[str, str], ...] = (
    (TRADEMARK_SYMBOL_PATTERN_TEXT, ""),
    (TRADEMARK_MARKER_PATTERN_TEXT, ""),
    (AMD_ENTITY_PATTERN_TEXT, "AMD"),
    (NVIDIA_ENTITY_PATTERN_TEXT, "NVIDIA"),
    (INTEL_ENTITY_PATTERN_TEXT, "Intel"),
    (BASE_CLOCK_SUFFIX_PATTERN_TEXT, ""),
    (MODEL_NUMBER_FILLER_PATTERN_TEXT, ""),
    (COMPUTE_CORES_SUFFIX_PATTERN_TEXT, ""),
    (NUMERIC_CORE_SUFFIX_PATTERN_TEXT, ""),
    (WORD_CORE_SUFFIX_PATTERN_TEXT, ""),
    (TRAILING_PROCESSOR_PATTERN_TEXT, ""),
    (SPACE_BEFORE_SEPARATOR_PATTERN_TEXT, r"\1"),
    (COLLAPSIBLE_WHITESPACE_PATTERN_TEXT, " "),
)


def build_device_display_name(value: JSONValue) -> str | None:
    name = coerce_optional_trimmed_str(value)
    if name is None:
        return None
    stripped = name
    for pattern_text, replacement in DISPLAY_NAME_RULES:
        stripped = re.sub(pattern_text, replacement, stripped, flags=re.IGNORECASE)
    stripped = stripped.strip(SURROUNDING_SEPARATORS)
    return stripped or " ".join(name.split())
