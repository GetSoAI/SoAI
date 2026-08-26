"""SoAI - Live token progress sampling for streamed inference [backend/orchestrator/execution/token_stream_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.token_rate_calculation import TOKEN_RATE_UPDATE_INTERVAL_MS
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.metrics.protocols import TokenStreamMetricsProtocol
    from core.openai.protocols_usage import CompletionTokenTranscriptProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = ("TokenStreamProgressSampler",)


class TokenStreamProgressSampler:
    def __init__(
        self,
        *,
        metrics: TokenStreamMetricsProtocol,
        prompt_token_counter: PromptTokenCounter,
        stream_id: str,
        plugin_name: str,
        model_name: str | None,
        token_estimation_profile: TokenEstimationProfile | None = None,
    ) -> None:
        self._metrics = metrics
        self._prompt_token_counter = prompt_token_counter
        self._stream_id = stream_id
        self._plugin = plugin_name.strip()
        self._model_name = model_name
        self._token_estimation_profile = token_estimation_profile
        self._last_sample_at_ms = 0
        self._started = False

    def begin(self) -> None:
        if not self._plugin or self._started:
            return
        self._started = True
        self._metrics.begin_token_stream(self._stream_id, self._plugin)

    def sample(
        self,
        transcript: CompletionTokenTranscriptProtocol,
        *,
        force: bool = False,
    ) -> None:
        if not self._plugin or not self._started:
            return
        observed_at_ms = monotonic_ms()
        if not force and observed_at_ms - self._last_sample_at_ms < TOKEN_RATE_UPDATE_INTERVAL_MS:
            return
        fragments = transcript.drain_completion_token_fragments()
        self._last_sample_at_ms = observed_at_ms
        if not fragments:
            return
        token_delta = self._prompt_token_counter.count_text_tokens(
            "".join(fragments),
            model_name=self._model_name,
            profile=self._token_estimation_profile,
        )
        self._metrics.record_token_stream_delta(
            self._stream_id,
            self._plugin,
            token_delta,
        )

    def finish(self) -> None:
        if not self._started:
            return
        self._started = False
        self._metrics.finish_token_stream(self._stream_id)
