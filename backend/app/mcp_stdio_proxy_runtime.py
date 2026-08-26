"""SoAI - MCP stdio proxy runtime [backend/app/mcp_stdio_proxy_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx2

from app.mcp_stdio_proxy_config import McpProxyConfig
from app.mcp_stdio_proxy_forwarding import (
    McpProxyState,
    inbound_worker,
    sse_loop,
    stdin_loop,
)
from app.mcp_stdio_proxy_http import (
    delete_session,
    perform_whoami_handshake,
)
from app.mcp_stdio_proxy_stdout import write_stdout_lines
from app.mcp_stdio_proxy_tasks import (
    finalize_stdio_proxy_tasks,
    stop_stdio_proxy_workers,
    wait_for_stdio_proxy_completion,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.http_transport import PinnedHost, PolicyPinnedAsyncHTTPTransport
from core.network.outbound_http_profiles import build_outbound_request_headers
from core.network.policy import enforce_url_local_only_policy
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, INTERACTIVE_TIMEOUT_SEC, SETUP_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("run_mcp_stdio_proxy",)

LOGGER_NAME = "SoAI.app.mcp_stdio_proxy_runtime"
OPERATION_PROXY_RUN = "app.mcp_stdio_proxy_runtime.run_mcp_stdio_proxy"
OPERATION_PROXY_DELETE_SESSION = "app.mcp_stdio_proxy_runtime.delete_session"
OPERATION_PROXY_WRITER_TASK = "app.mcp_stdio_proxy_runtime.writer_task"


async def run_mcp_stdio_proxy(config: McpProxyConfig) -> int:
    logger = get_logger(LOGGER_NAME)
    pinned_host = await enforce_url_local_only_policy(
        config.endpoint,
        source="MCP stdio proxy endpoint",
    )
    original_host = urlparse(config.endpoint).hostname
    if pinned_host and not original_host:
        raise ValidationError("MCP stdio proxy endpoint must include a hostname.")

    async def request_pinner(_request: httpx2.Request) -> PinnedHost | None:
        if not pinned_host or not original_host:
            return None
        return PinnedHost(pinned_ip=pinned_host, original_host=original_host)

    state = McpProxyState(session_id=None, protocol_version=None, session_ready=asyncio.Event())
    stdout_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=config.stdout_queue_size)
    inbound_queue: asyncio.Queue[JSONDict | None] = asyncio.Queue(maxsize=config.stdin_queue_size)
    timeout = httpx2.Timeout(
        connect=INTERACTIVE_TIMEOUT_SEC,
        read=SETUP_TIMEOUT_SEC,
        write=BACKGROUND_TIMEOUT_SEC,
        pool=INTERACTIVE_TIMEOUT_SEC,
    )
    async with httpx2.AsyncClient(
        headers=build_outbound_request_headers(profile_type="service_api"),
        timeout=timeout,
        transport=PolicyPinnedAsyncHTTPTransport(request_pinner=request_pinner),
        trust_env=False,
    ) as client:
        await perform_whoami_handshake(
            client,
            endpoint=config.endpoint,
            token=config.token,
            expected_user_id=config.expected_user_id,
        )
        writer_task = create_ephemeral_task(
            write_stdout_lines(stdout_queue),
            name="mcp_stdio_proxy.stdout_writer",
            log_exceptions=False,
        )
        sse_task = create_ephemeral_task(
            sse_loop(client, config, state, stdout_queue),
            name="mcp_stdio_proxy.sse_loop",
            log_exceptions=False,
        )
        workers = [
            create_ephemeral_task(
                inbound_worker(inbound_queue, client, config, state, stdout_queue),
                name=f"mcp_stdio_proxy.inbound_worker.{worker_index}",
                log_exceptions=False,
            )
            for worker_index in range(config.max_inflight)
        ]
        stdin_task = create_ephemeral_task(
            stdin_loop(client, config, state, stdout_queue, inbound_queue),
            name="mcp_stdio_proxy.stdin_loop",
            log_exceptions=False,
        )
        producer_tasks = (sse_task, *workers)
        monitored_tasks = (writer_task, *producer_tasks)
        cancelled = False
        had_error = False
        try:
            await wait_for_stdio_proxy_completion(
                stdin_task=stdin_task,
                inbound_queue=inbound_queue,
                background_tasks=monitored_tasks,
                logger=logger,
            )
            return 0
        except asyncio.CancelledError:
            cancelled = True
            raise
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="MCP stdio proxy run failed.",
                operation=OPERATION_PROXY_RUN,
            )
            had_error = True
            return 1
        finally:
            if (not cancelled) and (not had_error):
                await uncancel_then_cleanup(
                    stop_stdio_proxy_workers(
                        inbound_queue=inbound_queue,
                        worker_count=len(workers),
                        logger=logger,
                        operation=OPERATION_PROXY_RUN,
                    ),
                )
            if state.session_id is not None:
                try:
                    await uncancel_then_cleanup(
                        delete_session(
                            client,
                            endpoint=config.endpoint,
                            token=config.token,
                            session_id=state.session_id,
                        ),
                    )
                except HTTP_RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="MCP stdio proxy session cleanup failed (non-critical).",
                        operation=OPERATION_PROXY_DELETE_SESSION,
                        level="debug",
                    )
            await finalize_stdio_proxy_tasks(
                stdin_task=stdin_task,
                producer_tasks=producer_tasks,
                stdout_queue=stdout_queue,
                writer_task=writer_task,
                logger=logger,
                writer_operation=OPERATION_PROXY_WRITER_TASK,
            )
