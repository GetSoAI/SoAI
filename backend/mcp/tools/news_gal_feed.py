"""SoAI - GDELT Article List fallback search [backend/mcp/tools/news_gal_feed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.singleflight import AsyncSingleflight, ResultCopyMode
from core.concurrency.task_groups import cancel_and_await
from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.errors.external_service_exception import ExternalServiceError
from core.timing.epoch import epoch_seconds
from mcp.tools.error import MCPToolError
from mcp.tools.http_request_retries import (
    HttpRetryPolicy,
    build_retry_telemetry,
    bump_attempt,
    record_retry_error,
    record_retry_status,
    should_retry_for_exception,
    should_retry_for_status,
    sleep_before_retry,
)
from mcp.tools.news_gal_payload import (
    GalArticle,
    build_gal_provider_payload,
    parse_gal_payload,
)
from mcp.tools.news_gdelt_feed_http import read_gdelt_feed_response

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
    from mcp.tools.news_query import NewsRequest

__all__ = ("NewsArticleListSearch",)

_GAL_BASE_URL = "https://storage.googleapis.com/data.gdeltproject.org/gdeltv3/gal"
_GAL_START_YEAR = 2020
_GAL_LAG_MINUTES = 5
_GAL_WINDOW_BATCHES = 96
_GAL_BATCH_MINUTES = 15
_GAL_DOWNLOAD_CHUNK_SIZE = 4
_MAX_GAL_RESPONSE_BYTES = 2_097_152


def _new_batch_cache() -> TTLCache[str, tuple[GalArticle, ...]]:
    return TTLCache(
        TTLCacheDependencies(
            ttl_seconds=93_600.0,
            max_size=192,
        ),
    )


def _new_batch_singleflight() -> AsyncSingleflight[str, tuple[GalArticle, ...] | None]:
    return AsyncSingleflight(result_copier=ResultCopyMode.NONE)


def _gal_retry_policy() -> HttpRetryPolicy:
    return HttpRetryPolicy(
        retries=2,
        backoff_min_ms=1000,
        backoff_max_ms=4000,
        jitter_max_ms=500,
        retry_on_status=frozenset({502, 503, 504}),
        retry_on_timeouts=True,
        retry_on_request_errors=True,
    )


def _latest_complete_batch() -> datetime:
    safe_time = datetime.fromtimestamp(epoch_seconds(), tz=UTC) - timedelta(
        minutes=_GAL_LAG_MINUTES,
    )
    heartbeat_minute = (safe_time.minute // _GAL_BATCH_MINUTES) * _GAL_BATCH_MINUTES + 1
    candidate = safe_time.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=heartbeat_minute,
    )
    if candidate > safe_time:
        candidate -= timedelta(minutes=_GAL_BATCH_MINUTES)
    return candidate


def _batch_timestamps(request: NewsRequest) -> tuple[str, ...]:
    if request.target_date is not None:
        if request.target_date.year < _GAL_START_YEAR:
            return ()
        latest_batch = _latest_complete_batch()
        if request.target_date > latest_batch.date():
            return ()
        first_batch = datetime.combine(request.target_date, datetime.min.time(), tzinfo=UTC)
        first_batch += timedelta(minutes=1)
        last_batch = first_batch + timedelta(
            minutes=_GAL_BATCH_MINUTES * (_GAL_WINDOW_BATCHES - 1),
        )
        if request.target_date == latest_batch.date():
            last_batch = latest_batch
        batch_count = int((last_batch - first_batch) / timedelta(minutes=_GAL_BATCH_MINUTES)) + 1
        return tuple(
            (last_batch - timedelta(minutes=_GAL_BATCH_MINUTES * index)).strftime(
                "%Y%m%d%H%M00",
            )
            for index in range(batch_count)
        )
    latest_batch = _latest_complete_batch()
    return tuple(
        (latest_batch - timedelta(minutes=_GAL_BATCH_MINUTES * index)).strftime(
            "%Y%m%d%H%M00",
        )
        for index in range(_GAL_WINDOW_BATCHES)
    )


class NewsArticleListSearch:
    def __init__(self) -> None:
        self._batch_cache = _new_batch_cache()
        self._batch_singleflight = _new_batch_singleflight()

    async def _read_batch_response(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        timestamp: str,
        timeout_sec: float,
    ) -> tuple[bytes, int]:
        url = f"{_GAL_BASE_URL}/{timestamp}.gal.json.gz"
        telemetry = build_retry_telemetry()
        policy = _gal_retry_policy()
        attempts_total = policy.retries + 1
        for attempt_index in range(1, attempts_total + 1):
            bump_attempt(telemetry)
            try:
                body, status_code = await read_gdelt_feed_response(
                    utility_tools,
                    url=url,
                    timeout_sec=timeout_sec,
                    max_response_bytes=_MAX_GAL_RESPONSE_BYTES,
                )
            except httpx2.HTTPError as exception:
                record_retry_error(telemetry, error=str(exception))
                if attempt_index <= policy.retries and should_retry_for_exception(
                    policy=policy,
                    exception=exception,
                ):
                    await sleep_before_retry(
                        telemetry,
                        policy=policy,
                        attempt_index=attempt_index,
                    )
                    continue
                raise ExternalServiceError("GDELT Article List request failed.") from exception
            except MCPToolError as exception:
                if exception.rpc_code == -32602:
                    raise
                raise ExternalServiceError(exception.message) from exception
            record_retry_status(telemetry, status_code=status_code)
            if status_code in {200, 404}:
                return body, status_code
            if attempt_index <= policy.retries and should_retry_for_status(
                policy=policy,
                status_code=status_code,
            ):
                await sleep_before_retry(
                    telemetry,
                    policy=policy,
                    attempt_index=attempt_index,
                )
                continue
            raise ExternalServiceError(f"GDELT Article List returned HTTP {status_code}.")
        raise ExternalServiceError("GDELT Article List request failed.")

    async def _fetch_batch(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        timestamp: str,
        timeout_sec: float,
    ) -> tuple[GalArticle, ...] | None:
        body, status_code = await self._read_batch_response(
            utility_tools,
            timestamp=timestamp,
            timeout_sec=timeout_sec,
        )
        if status_code == 404:
            return None
        articles = parse_gal_payload(body)
        self._batch_cache.put(timestamp, articles)
        return articles

    async def _load_batch(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        timestamp: str,
        timeout_sec: float,
    ) -> tuple[GalArticle, ...] | None:
        cached = self._batch_cache.get(timestamp)
        if cached is not None:
            return cached
        return await self._batch_singleflight.execute_or_wait(
            timestamp,
            lambda: self._fetch_batch(
                utility_tools,
                timestamp=timestamp,
                timeout_sec=timeout_sec,
            ),
        )

    async def _load_chunk(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        timestamps: tuple[str, ...],
        timeout_sec: float,
    ) -> list[tuple[GalArticle, ...] | None]:
        batch_tasks = [
            create_ephemeral_task(
                self._load_batch(
                    utility_tools,
                    timestamp=timestamp,
                    timeout_sec=timeout_sec,
                ),
                log_exceptions=False,
            )
            for timestamp in timestamps
        ]
        try:
            return list(
                await asyncio.gather(
                    *batch_tasks,
                    return_exceptions=False,
                )
            )
        finally:
            await cancel_and_await(batch_tasks)

    async def search(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        request: NewsRequest,
        timeout_sec: float,
    ) -> JSONDict:
        timestamps = _batch_timestamps(request)
        collected_batches: list[tuple[GalArticle, ...]] = []
        chunk_size = 1 if request.top_headlines else _GAL_DOWNLOAD_CHUNK_SIZE
        for offset in range(0, len(timestamps), chunk_size):
            chunk = timestamps[offset : offset + chunk_size]
            loaded = await self._load_chunk(
                utility_tools,
                timestamps=chunk,
                timeout_sec=timeout_sec,
            )
            collected_batches.extend(batch for batch in loaded if batch is not None)
            payload = build_gal_provider_payload(tuple(collected_batches), request)
            articles = payload.get("articles")
            if request.top_headlines and isinstance(articles, list) and articles:
                return payload
            if isinstance(articles, list) and len(articles) >= request.max_results:
                return payload
        return build_gal_provider_payload(tuple(collected_batches), request)
