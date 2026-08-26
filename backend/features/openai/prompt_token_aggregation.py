"""SoAI - Virtual-model prompt occupancy aggregation [backend/features/openai/prompt_token_aggregation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import PromptOccupancy

__all__ = ("aggregate_prompt_occupancies",)


def aggregate_prompt_occupancies(
    occupancies: list[PromptOccupancy],
    *,
    max_counted_tokens: int,
) -> PromptOccupancy:
    if not occupancies:
        raise ValidationError("At least one prompt occupancy is required.")
    if max_counted_tokens <= 0:
        raise ValidationError("Maximum counted tokens must be positive.")
    maximum_tokens = max(occupancy.prompt_tokens for occupancy in occupancies)
    if maximum_tokens > max_counted_tokens:
        return PromptOccupancy(
            prompt_tokens=max_counted_tokens,
            capped=True,
            capped_reason="token_limit",
            precision="estimated",
        )
    capped_occupancies = [occupancy for occupancy in occupancies if occupancy.capped]
    if capped_occupancies:
        capped_reason = capped_occupancies[0].capped_reason
        return PromptOccupancy(
            prompt_tokens=maximum_tokens,
            capped=True,
            capped_reason=capped_reason,
            precision="estimated",
        )
    exact_counts = {
        occupancy.prompt_tokens for occupancy in occupancies if occupancy.precision == "exact"
    }
    all_exact = len(exact_counts) == len({maximum_tokens}) and all(
        occupancy.precision == "exact" for occupancy in occupancies
    )
    return PromptOccupancy(
        prompt_tokens=maximum_tokens,
        capped=False,
        capped_reason=None,
        precision="exact" if all_exact else "estimated",
    )
