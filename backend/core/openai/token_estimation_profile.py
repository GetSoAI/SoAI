"""SoAI - Token estimation profile [backend/core/openai/token_estimation_profile.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.validation.numbers import coerce_optional_float_from_json
from core.validation.strings import coerce_required_non_empty_str

__all__ = ("TokenEstimationProfile",)


def _require_token_character_floor(value: float | None) -> float:
    floor = coerce_optional_float_from_json(value)
    if floor is None:
        raise ValidationError("Approximate token profiles require a numeric character floor.")
    if floor <= 0.0:
        raise ValidationError("Approximate token profile character floor must be positive.")
    return floor


@dataclass(frozen=True, slots=True)
class TokenEstimationProfile:
    encoding_name: str
    is_approximate: bool
    chars_per_token_floor: float | None = None

    def __post_init__(self) -> None:
        coerce_required_non_empty_str(self.encoding_name, label="Token profile encoding name")
        if not isinstance(self.is_approximate, bool):
            raise ValidationError("Token profile approximation flag must be a boolean.")
        if not self.is_approximate and self.chars_per_token_floor is not None:
            raise ValidationError("Exact token profiles must not define a character floor.")
        if self.is_approximate:
            _require_token_character_floor(self.chars_per_token_floor)

    @staticmethod
    def exact(encoding_name: str) -> TokenEstimationProfile:
        resolved_encoding_name = coerce_required_non_empty_str(
            encoding_name,
            label="Token profile encoding name",
        )
        return TokenEstimationProfile(
            encoding_name=resolved_encoding_name,
            is_approximate=False,
            chars_per_token_floor=None,
        )

    @staticmethod
    def approximate(
        *,
        encoding_name: str,
        chars_per_token_floor: float,
    ) -> TokenEstimationProfile:
        resolved_encoding_name = coerce_required_non_empty_str(
            encoding_name,
            label="Token profile encoding name",
        )
        resolved_character_floor = _require_token_character_floor(chars_per_token_floor)
        return TokenEstimationProfile(
            encoding_name=resolved_encoding_name,
            is_approximate=True,
            chars_per_token_floor=resolved_character_floor,
        )
