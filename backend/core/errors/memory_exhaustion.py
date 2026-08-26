"""SoAI - CPU and accelerator memory exhaustion classification [backend/core/errors/memory_exhaustion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exceptions import (
    AcceleratorMemoryExhaustedError,
    SystemMemoryExhaustedError,
)

if TYPE_CHECKING:
    from typing import Literal

    type MemoryExhaustionType = Literal["accelerator", "system"]

__all__ = (
    "ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE",
    "SYSTEM_MEMORY_EXHAUSTED_MESSAGE",
    "classify_memory_exhaustion",
    "raise_for_memory_exhaustion",
    "resolve_memory_exhaustion_message",
)

ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE = (
    "The model could not load or complete the request because GPU or accelerator memory "
    "was exhausted. Free accelerator memory or reduce context length, batch size, GPU "
    "layers, or speculative drafting, then retry."
)
SYSTEM_MEMORY_EXHAUSTED_MESSAGE = (
    "The model could not load or complete the request because system memory was exhausted. "
    "Free RAM or reduce context length, batch size, or concurrency, then retry."
)

ACCELERATOR_MEMORY_MARKERS: tuple[str, ...] = (
    "cuda out of memory",
    "cuda error: out of memory",
    "cudamalloc failed: out of memory",
    "hip out of memory",
    "hiperroroutofmemory",
    "mps backend out of memory",
    "mps out of memory",
    "xpu out of memory",
    "out of device memory",
    "failed to allocate device memory",
    "failed to allocate vulkan",
    "vulkan out of memory",
    "vk_error_out_of_device_memory",
    "accelerator memory was exhausted",
    "ran out of accelerator memory",
)
SYSTEM_MEMORY_MARKERS: tuple[str, ...] = (
    "memoryerror",
    "std::bad_alloc",
    "bad allocation",
    "cannot allocate memory",
    "not enough memory",
    "enomem",
    "errno 12",
    "cpu out of memory",
    "model requires more system memory",
    "system memory was exhausted",
    "ram was exhausted",
    "ran out of system memory",
)


def classify_memory_exhaustion(diagnostic: str) -> MemoryExhaustionType | None:
    normalized = str(diagnostic or "").casefold()
    if any(marker in normalized for marker in ACCELERATOR_MEMORY_MARKERS):
        return "accelerator"
    if any(marker in normalized for marker in SYSTEM_MEMORY_MARKERS):
        return "system"
    return None


def raise_for_memory_exhaustion(diagnostic: str) -> None:
    exhaustion_type = classify_memory_exhaustion(diagnostic)
    if exhaustion_type == "accelerator":
        raise AcceleratorMemoryExhaustedError(ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE)
    if exhaustion_type == "system":
        raise SystemMemoryExhaustedError(SYSTEM_MEMORY_EXHAUSTED_MESSAGE)


def resolve_memory_exhaustion_message(code: str | int | None) -> str | None:
    if code == ErrorType.ACCELERATOR_MEMORY_EXHAUSTED.value:
        return ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE
    if code == ErrorType.SYSTEM_MEMORY_EXHAUSTED.value:
        return SYSTEM_MEMORY_EXHAUSTED_MESSAGE
    return None
