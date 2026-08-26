"""SoAI - Password strength evaluation and validation [backend/core/validation/password_strength.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final

from core.errors.exceptions import ValidationError

__all__ = (
    "PasswordStrength",
    "PasswordStrengthEvaluator",
    "PasswordStrengthResult",
    "evaluate_password_strength",
    "validate_password_strength",
    "validate_strong_password",
    "validate_very_strong_password",
)


class PasswordStrength(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass(frozen=True, slots=True)
class PasswordStrengthResult:
    strength: PasswordStrength
    score: int
    feedback: list[str]


class PasswordStrengthEvaluator:
    MIN_LENGTH: Final[int] = 8
    MAX_LENGTH: Final[int] = 1024
    LENGTH_WEIGHT: Final[int] = 2
    VARIETY_WEIGHT: Final[int] = 3
    COMPLEXITY_WEIGHT: Final[int] = 2
    PATTERN_WEIGHT: Final[int] = 3
    LOWER_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z]")
    UPPER_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Z]")
    DIGIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\d")
    SPECIAL_PATTERN: Final[re.Pattern[str]] = re.compile(r'[!@#$%^&*(),.?":{}|<>]')
    WEAK_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
        re.compile(r"^(?:password|admin|user|root|welcome|123456|qwerty|abc123)", re.IGNORECASE),
        re.compile(r"(\w)\1{2,}"),
        re.compile(r"(.)\1{3,}"),
        re.compile(
            r"^(?:123|234|345|456|567|678|789|890|abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)",
            re.IGNORECASE,
        ),
    )

    def evaluate(self, password: str) -> PasswordStrengthResult:
        if not password:
            raise ValidationError("Password cannot be empty.")

        if len(password) > self.MAX_LENGTH:
            raise ValidationError(
                f"Password exceeds maximum length of {self.MAX_LENGTH} characters.",
            )

        length_score = self._evaluate_length(password)
        variety_score = self._evaluate_character_variety(password)
        complexity_score = self._evaluate_complexity(password)
        pattern_score = self._evaluate_patterns(password)

        weighted_score = (
            length_score * self.LENGTH_WEIGHT
            + variety_score * self.VARIETY_WEIGHT
            + complexity_score * self.COMPLEXITY_WEIGHT
            + pattern_score * self.PATTERN_WEIGHT
        )
        maximum_score = (
            3 * self.LENGTH_WEIGHT
            + 4 * self.VARIETY_WEIGHT
            + 3 * self.COMPLEXITY_WEIGHT
            + 3 * self.PATTERN_WEIGHT
        )
        total_score = (weighted_score * 10) // maximum_score

        strength = self._score_to_strength(total_score)
        feedback = self._generate_feedback(
            password,
            length_score,
            variety_score,
            complexity_score,
            pattern_score,
        )

        return PasswordStrengthResult(strength=strength, score=total_score, feedback=feedback)

    def _evaluate_length(self, password: str) -> int:
        password_length = len(password)
        if password_length < self.MIN_LENGTH:
            return 0
        if password_length < 12:
            return 1
        if password_length < 16:
            return 2
        return 3

    def _evaluate_character_variety(self, password: str) -> int:
        has_lower = bool(self.LOWER_PATTERN.search(password))
        has_upper = bool(self.UPPER_PATTERN.search(password))
        has_digit = bool(self.DIGIT_PATTERN.search(password))
        has_special = bool(self.SPECIAL_PATTERN.search(password))
        return sum((has_lower, has_upper, has_digit, has_special))

    def _evaluate_complexity(self, password: str) -> int:
        password_length = len(password)
        variety_count = self._evaluate_character_variety(password)
        if password_length >= 16 and variety_count >= 3:
            return 3
        if password_length >= 12 and variety_count >= 2:
            return 2
        if variety_count >= 2:
            return 1
        return 0

    def _evaluate_patterns(self, password: str) -> int:
        for pattern in self.WEAK_PATTERNS:
            if pattern.search(password):
                return 0

        if self._has_sequence(password):
            return 1

        if self._has_keyboard_pattern(password):
            return 1

        return 3

    def _has_sequence(self, password: str) -> bool:
        for character_index in range(len(password) - 2):
            if ord(password[character_index]) + 1 == ord(password[character_index + 1]) and ord(
                password[character_index + 1],
            ) + 1 == ord(password[character_index + 2]):
                return True
            if ord(password[character_index]) - 1 == ord(password[character_index + 1]) and ord(
                password[character_index + 1],
            ) - 1 == ord(password[character_index + 2]):
                return True
        return False

    def _has_keyboard_pattern(self, password: str) -> bool:
        keyboard_rows = (
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
        )
        password_lower = password.lower()

        for keyboard_row in keyboard_rows:
            for character_index in range(len(keyboard_row) - 3):
                keyboard_pattern = keyboard_row[character_index : character_index + 4]
                if keyboard_pattern in password_lower or keyboard_pattern[::-1] in password_lower:
                    return True

        return False

    def _score_to_strength(self, score: int) -> PasswordStrength:
        if score <= 2:
            return PasswordStrength.WEAK
        if score <= 5:
            return PasswordStrength.MEDIUM
        if score <= 7:
            return PasswordStrength.STRONG
        return PasswordStrength.VERY_STRONG

    def _generate_feedback(
        self,
        password: str,
        length_score: int,
        variety_score: int,
        complexity_score: int,
        pattern_score: int,
    ) -> list[str]:
        feedback_messages: list[str] = []

        if length_score == 0:
            feedback_messages.append("Password is too short (minimum 8 characters)")
        elif length_score == 1:
            feedback_messages.append("Consider making your password longer (12+ characters)")

        if variety_score < 2:
            missing_components: list[str] = []
            if not self.LOWER_PATTERN.search(password):
                missing_components.append("lowercase letters")
            if not self.UPPER_PATTERN.search(password):
                missing_components.append("uppercase letters")
            if not self.DIGIT_PATTERN.search(password):
                missing_components.append("numbers")
            if not self.SPECIAL_PATTERN.search(password):
                missing_components.append("special characters")

            if missing_components:
                feedback_messages.append(f"Consider adding {', '.join(missing_components)}")

        if complexity_score == 0 and variety_score >= 2:
            feedback_messages.append(
                "Make your password more complex by using longer character combinations",
            )

        if pattern_score < 3:
            if self._has_sequence(password):
                feedback_messages.append("Avoid simple sequences like '123' or 'abc'")
            if self._has_keyboard_pattern(password):
                feedback_messages.append("Avoid keyboard patterns like 'qwerty' or 'asdf'")

            for pattern in self.WEAK_PATTERNS:
                if pattern.search(password):
                    feedback_messages.append("Avoid common password patterns")
                    break

        return feedback_messages


def evaluate_password_strength(password: str) -> PasswordStrengthResult:
    return PasswordStrengthEvaluator().evaluate(password)


def validate_password_strength(
    password: str,
    min_strength: PasswordStrength = PasswordStrength.MEDIUM,
) -> None:
    result = evaluate_password_strength(password)
    strength_order = {
        PasswordStrength.WEAK: 0,
        PasswordStrength.MEDIUM: 1,
        PasswordStrength.STRONG: 2,
        PasswordStrength.VERY_STRONG: 3,
    }

    if strength_order[result.strength] < strength_order[min_strength]:
        feedback_text = ", ".join(result.feedback) if result.feedback else "password is too weak"
        raise ValidationError(f"Password validation failed: {feedback_text}")


def validate_strong_password(password: str) -> None:
    validate_password_strength(password, PasswordStrength.STRONG)


def validate_very_strong_password(password: str) -> None:
    validate_password_strength(password, PasswordStrength.VERY_STRONG)
