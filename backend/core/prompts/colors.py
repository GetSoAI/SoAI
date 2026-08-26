"""SoAI - Prompt color validation [backend/core/prompts/colors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "DEFAULT_PROMPT_COLOR",
    "PROMPT_COLOR_CHOICES",
    "validate_prompt_color",
)

DEFAULT_PROMPT_COLOR = "Yellow"
PROMPT_COLOR_CHOICES: tuple[str, ...] = ("Red", "Yellow", "Purple", "Green", "Blue")


def validate_prompt_color(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    normalized_candidate = candidate.lower()
    for choice in PROMPT_COLOR_CHOICES:
        if choice.lower() == normalized_candidate:
            return choice
    message = "".join(
        (
            f"Unsupported prompt color '{candidate}'. Expected one of: ",
            f"{', '.join(PROMPT_COLOR_CHOICES)}.",
        ),
    )
    raise ValidationError(message)
