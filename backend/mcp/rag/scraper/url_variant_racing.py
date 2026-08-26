"""SoAI - URL variant racing for web scraping [backend/mcp/rag/scraper/url_variant_racing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.rag.scraper.fetch_progress import invoke_progress_callback

if TYPE_CHECKING:
    from mcp.rag.scraper.internal_protocols import (
        ProgressCallbackProtocol,
        WebContentFetcherProtocol,
    )

    FetchResult = tuple[bytes, str, str, str | None]

__all__ = ("race_url_variants",)

LOGGER_NAME = "SoAI.mcp.rag.url_variant_racing"
OPERATION = "mcp.rag.scraper.race_url_variants.variant_result"


def _stagger_timeout_seconds(min_stagger_sec: float, max_stagger_sec: float) -> float:
    return secrets.SystemRandom().uniform(min_stagger_sec, max_stagger_sec)


def _select_acceptable_success(
    results: dict[int, FetchResult],
    errors: dict[int, Exception],
    *,
    grace_elapsed: bool,
) -> int | None:
    if not results:
        return None
    best = min(results.keys())
    lower_pending = any(index not in results and index not in errors for index in range(best))
    if not lower_pending:
        return best
    if grace_elapsed:
        return best
    return None


def _raise_variant_failure(url: str, url_variants: list[str], errors: dict[int, Exception]) -> None:
    for index in range(len(url_variants)):
        last_exception = errors.get(index)
        if last_exception is None:
            continue
        if isinstance(last_exception, httpx2.HTTPStatusError):
            raise ValidationError(
                f"HTTP error fetching {url}: {last_exception.response.status_code} (tried {len(url_variants)} URL variants)",
            ) from last_exception
        if isinstance(last_exception, httpx2.RequestError):
            raise ValidationError(
                f"Network error fetching {url}: {last_exception} (tried {len(url_variants)} URL variants)",
            ) from last_exception
        if isinstance(last_exception, TimeoutError):
            raise TimeoutError(f"{last_exception}") from last_exception
        if isinstance(last_exception, ValidationError):
            raise ValidationError(
                f"Failed to fetch {url}: {last_exception} (tried {len(url_variants)} URL variants)",
            ) from last_exception
        raise ValidationError(
            f"Failed to fetch {url}: {type(last_exception).__name__}: {last_exception} (tried {len(url_variants)} URL variants)",
        ) from last_exception
    raise ValidationError(f"Failed to fetch {url}: all variants failed")


async def race_url_variants(
    self: WebContentFetcherProtocol,
    url: str,
    *,
    url_variants: list[str],
    progress_callback: ProgressCallbackProtocol | None,
) -> FetchResult:
    logger = get_logger(LOGGER_NAME)
    min_stagger_sec = 0.2
    max_stagger_sec = 0.6
    priority_grace_sec = 0.3

    tasks: list[asyncio.Task[FetchResult]] = []
    index_by_task: dict[asyncio.Task[FetchResult], int] = {}
    pending: set[asyncio.Task[FetchResult]] = set()
    results: dict[int, FetchResult] = {}
    errors: dict[int, Exception] = {}
    first_success_at: float | None = None

    best_active_index = 0

    def _recompute_best_active_index(*, started_count: int) -> None:
        nonlocal best_active_index
        for index in range(started_count):
            if index not in errors:
                best_active_index = index
                return
        best_active_index = max(0, started_count - 1)

    async def _wrapped_fetch(variant_url: str, index: int) -> FetchResult:
        async def _conditional_progress(current: int, total: int | None, url: str) -> None:
            if index == best_active_index and progress_callback:
                await invoke_progress_callback(progress_callback, current, total, url)

        return await self.fetch_raw(variant_url, progress_callback=_conditional_progress)

    def _drain_completed(
        completed: set[asyncio.Task[FetchResult]],
        started_count: int,
    ) -> None:
        for task in completed:
            idx = index_by_task.get(task, -1)
            if idx < 0:
                continue
            if idx in results or idx in errors:
                continue
            try:
                results[idx] = task.result()
            except (
                httpx2.HTTPStatusError,
                httpx2.RequestError,
                TimeoutError,
                ValidationError,
            ) as exception:
                errors[idx] = exception
            except HTTP_RECOVERABLE_EXCEPTIONS as exception_recoverable:
                coerced = coerce_to_soai_error(
                    exception_recoverable,
                    operation="mcp.rag.scraper.race_url_variants.variant_result",
                )
                log_handled_exception(
                    logger,
                    coerced,
                    message="URL variant fetch raised unexpected exception (non-critical).",
                    operation=OPERATION,
                    details={
                        "url": url,
                        "variant_url": url_variants[idx] if 0 <= idx < len(url_variants) else None,
                        "variant_index": idx,
                    },
                    level="debug",
                )
                errors[idx] = coerced
        _recompute_best_active_index(started_count=started_count)

    try:
        for index, variant_url in enumerate(url_variants):
            task = create_ephemeral_task(
                _wrapped_fetch(variant_url, index),
                log_exceptions=False,
            )
            tasks.append(task)
            index_by_task[task] = index
            pending.add(task)

            stagger_timeout = _stagger_timeout_seconds(min_stagger_sec, max_stagger_sec)
            done, pending = await asyncio.wait(
                pending,
                timeout=stagger_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            _drain_completed(done, started_count=index + 1)
            if first_success_at is None and results:
                first_success_at = time.monotonic()
            grace_elapsed = (
                False
                if first_success_at is None
                else (time.monotonic() - first_success_at) >= priority_grace_sec
            )
            acceptable = _select_acceptable_success(results, errors, grace_elapsed=grace_elapsed)
            if acceptable is not None:
                return results[acceptable]

        while pending:
            done, pending = await asyncio.wait(
                pending,
                timeout=max_stagger_sec,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                continue
            _drain_completed(done, started_count=len(url_variants))
            if first_success_at is None and results:
                first_success_at = time.monotonic()
            grace_elapsed = (
                False
                if first_success_at is None
                else (time.monotonic() - first_success_at) >= priority_grace_sec
            )
            acceptable = _select_acceptable_success(results, errors, grace_elapsed=grace_elapsed)
            if acceptable is not None:
                return results[acceptable]
    finally:
        if tasks:
            await cancel_and_await(
                tasks,
                logger=logger,
                task_label="URL variant fetch tasks",
                message="Cancelling URL variant fetch tasks...",
                log_level=logging.DEBUG,
            )
            for task in tasks:
                if task.cancelled():
                    continue
                exception = task.exception()
                if exception is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message="URL variant fetch task raised during cancellation cleanup (non-critical).",
                        operation=OPERATION,
                        level="debug",
                    )

    _raise_variant_failure(url, url_variants, errors)
    raise StateError("Unreachable: variant racing did not return or raise.")
