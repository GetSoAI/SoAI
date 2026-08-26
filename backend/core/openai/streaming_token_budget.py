"""SoAI - Streaming token budget tracker for quota enforcement [backend/core/openai/streaming_token_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_counter import PromptTokenCounter
from core.quotas.token_reservation_payloads import (
    resolve_streaming_completion_token_limit,
)
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = ("StreamingTokenBudgetTracker", "build_streaming_token_budget")

_EXACT_MODE_PROXIMITY_TOKENS = 256


class StreamingTokenBudgetTracker:
    __slots__ = (
        "_exact_tokens",
        "_incremental_tokens",
        "_model_name",
        "_text_parts",
        "_token_counter",
        "_token_limit",
    )

    def __init__(
        self,
        token_counter: PromptTokenCounter,
        *,
        token_limit: int,
        model_name: str | None = None,
    ) -> None:
        if not is_strict_int(token_limit):
            raise ValidationError("token_limit must be an integer.")
        if token_limit < 0:
            raise ValidationError("token_limit must be >= 0.")
        self._token_counter = token_counter
        self._token_limit = int(token_limit)
        self._model_name = model_name
        self._text_parts: list[str] = []
        self._incremental_tokens = 0
        self._exact_tokens: int | None = None

    def add_texts(self, deltas: Iterable[str]) -> bool:
        candidate_parts: list[str] = []
        for delta in deltas:
            if isinstance(delta, str) and delta:
                candidate_parts.append(delta)
        if not candidate_parts:
            return self._is_over_limit()
        return self._ingest_parts(candidate_parts)

    def _is_over_limit(self) -> bool:
        exact = self._exact_tokens
        if exact is not None:
            return exact > self._token_limit
        return self._incremental_tokens > self._token_limit

    def _compute_exact(self) -> int:
        full_text = "".join(self._text_parts)
        exact = self._token_counter.count_text_tokens(full_text, model_name=self._model_name)
        self._exact_tokens = exact
        return exact

    def _ingest_parts(self, parts: list[str]) -> bool:
        self._text_parts.extend(parts)

        if self._exact_tokens is not None:
            return self._compute_exact() > self._token_limit

        for part in parts:
            self._incremental_tokens += self._token_counter.count_text_tokens(
                part,
                model_name=self._model_name,
            )

        if self._incremental_tokens + _EXACT_MODE_PROXIMITY_TOKENS >= self._token_limit:
            return self._compute_exact() > self._token_limit

        return False


def build_streaming_token_budget(
    quota_reservation: JSONDict,
    prompt_tokens: int | None,
    config: ConfigProtocol,
    prompt_token_counter: PromptTokenCounter,
    *,
    model_name: str | None = None,
) -> StreamingTokenBudgetTracker | None:
    token_limit = resolve_streaming_completion_token_limit(
        quota_reservation=quota_reservation,
        prompt_tokens=prompt_tokens,
        default_overage_units=int(config.get_int("API.OPENAI.KEY_QUOTAS.STREAMING_OVERAGE_TOKENS")),
    )
    if token_limit is None:
        return None
    return StreamingTokenBudgetTracker(
        prompt_token_counter,
        token_limit=token_limit,
        model_name=model_name,
    )
