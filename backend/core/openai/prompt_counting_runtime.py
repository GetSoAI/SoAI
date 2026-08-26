"""SoAI - Bounded prompt-token execution runtime [backend/core/openai/prompt_counting_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
    shutdown_bounded_pool_executor,
)
from core.di.validation import require_dependencies
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC

__all__ = (
    "PromptCountingRuntime",
    "PromptCountingRuntimeDependencies",
)


@dataclass(frozen=True, slots=True)
class PromptCountingRuntimeDependencies:
    blocking_pool: BoundedBlockingPool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PromptCountingRuntimeDependencies",
            blocking_pool=self.blocking_pool,
        )


class PromptCountingRuntime:
    def __init__(self, deps: PromptCountingRuntimeDependencies) -> None:
        self._deps = deps

    async def run[*Arguments, ResultT](
        self,
        function: Callable[[*Arguments], ResultT],
        *args: *Arguments,
    ) -> ResultT:
        return await run_bounded_blocking_call(
            self._deps.blocking_pool,
            function,
            *args,
            total_timeout_sec=LONG_REQUEST_TIMEOUT_SEC,
        )

    def shutdown(self) -> None:
        shutdown_bounded_pool_executor(self._deps.blocking_pool)
