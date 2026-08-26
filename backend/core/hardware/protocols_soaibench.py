"""SoAI - SoAIBench protocol definitions [backend/core/hardware/protocols_soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict

__all__ = ()


class DatabaseSoAIBenchProtocol(Protocol):
    async def clear_hardware_history(self) -> None: ...

    async def create_soaibench_run(self, run: JSONDict) -> None: ...

    async def update_soaibench_heartbeat(
        self,
        *,
        run_id: str,
        last_heartbeat_at_ms: int,
        sample_count: int,
        summary_json: str | None,
    ) -> None: ...

    async def finish_soaibench_run(self, run_id: str, fields: JSONDict) -> None: ...

    async def request_soaibench_stop(
        self,
        *,
        run_id: str,
        stop_requested_at_ms: int,
    ) -> bool: ...

    async def get_soaibench_run_for_user(
        self,
        *,
        user_id: int,
        run_id: str,
    ) -> JSONDict | None: ...

    async def list_soaibench_history(
        self,
        *,
        user_id: int,
        identity: JSONDict,
        limit: int,
    ) -> list[JSONDict]: ...

    async def list_soaibench_history_export(
        self,
        *,
        user_id: int,
        identity: JSONDict,
    ) -> list[JSONDict]: ...

    async def list_soaibench_recent_for_user(
        self,
        *,
        user_id: int,
        limit: int,
    ) -> list[JSONDict]: ...

    async def reconcile_soaibench_running_rows(self, completed_at_ms: int) -> int: ...


class SoAIBenchServiceProtocol(Protocol):
    async def reconcile_startup(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def reset_history(self) -> None: ...

    async def start_run(
        self,
        *,
        device_id: str,
        profile: str,
        created_by_user_id: int,
        created_by_tool: str,
        benchmark_mode: str | None = None,
        temperature_limit_celsius: float | None = None,
        deferred_tool_activity: DeferredToolCallActivity | None = None,
    ) -> JSONDict: ...

    async def get_run(self, *, run_id: str, user_id: int) -> JSONDict: ...

    async def stop_run(self, *, run_id: str, user_id: int) -> JSONDict: ...

    async def list_history(self, *, device_id: str, user_id: int, limit: int) -> JSONDict: ...

    async def export_history_csv(
        self,
        *,
        device_id: str,
        user_id: int,
    ) -> tuple[str, AsyncIterator[bytes]]: ...

    async def list_runs(self, *, user_id: int, limit: int) -> JSONDict: ...
