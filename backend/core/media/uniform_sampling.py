"""SoAI - Deterministic uniform index selection [backend/core/media/uniform_sampling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("select_uniform_indices",)


def _rounded_ratio(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    doubled_remainder = remainder * 2
    if doubled_remainder < denominator:
        return quotient
    if doubled_remainder > denominator or quotient % 2:
        return quotient + 1
    return quotient


def select_uniform_indices(total: int, selected: int) -> tuple[int, ...]:
    if total <= 0 or selected <= 0:
        raise ValidationError("Uniform sampling counts must be positive.")
    if selected >= total:
        return tuple(range(total))
    if selected == 1:
        return (_rounded_ratio(total - 1, 2),)
    return tuple(_rounded_ratio(index * (total - 1), selected - 1) for index in range(selected))
