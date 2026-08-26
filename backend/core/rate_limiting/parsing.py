"""SoAI - Core rate limit string parsing [backend/core/rate_limiting/parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from functools import lru_cache

from core.errors.exceptions import ValidationError
from core.rate_limiting.definitions import RateLimitRule

__all__ = ("parse_rate_limit_rules",)


@lru_cache(maxsize=1)
def _limit_pattern() -> re.Pattern[str]:
    return re.compile(
        r"^\s*(?P<amount>[0-9]+)\s*(?:(?:/)|(?:per\s+))\s*(?P<unit>[A-Za-z]+)\s*$",
        re.IGNORECASE,
    )


@lru_cache(maxsize=1)
def _separators_pattern() -> re.Pattern[str]:
    return re.compile(r"[,;\n]+")


def _resolve_window_seconds(unit_text: str) -> int | None:
    if unit_text in {"s", "sec", "secs", "second", "seconds"}:
        return 1
    if unit_text in {"m", "min", "mins", "minute", "minutes"}:
        return 60
    if unit_text in {"h", "hr", "hrs", "hour", "hours"}:
        return 3600
    if unit_text in {"d", "day", "days"}:
        return 86400
    return None


def _parse_single_rule(raw_rule: str) -> RateLimitRule:
    match = _limit_pattern().fullmatch(raw_rule)
    if match is None:
        raise ValidationError(f"Invalid rate limit rule: {raw_rule!r}.")
    amount_text = match.group("amount")
    unit_text = match.group("unit").strip().lower()
    amount = int(amount_text)
    if amount < 1:
        raise ValidationError(f"Rate limit amount must be positive: {raw_rule!r}.")
    window_seconds = _resolve_window_seconds(unit_text)
    if window_seconds is None:
        raise ValidationError(f"Unsupported rate limit unit: {unit_text}.")
    return RateLimitRule(
        amount=amount,
        window_seconds=window_seconds,
        label=f"{amount}/{unit_text}",
    )


def parse_rate_limit_rules(limit_string: str) -> tuple[RateLimitRule, ...]:
    normalized = limit_string.strip()
    if not normalized:
        return ()
    rules: list[RateLimitRule] = []
    for raw_part in _separators_pattern().split(normalized):
        stripped = raw_part.strip()
        if not stripped:
            continue
        rules.append(_parse_single_rule(stripped))
    return tuple(rules)
