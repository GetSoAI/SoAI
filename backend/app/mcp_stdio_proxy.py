"""SoAI - MCP stdio transport proxy [backend/app/mcp_stdio_proxy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys

from app.mcp_stdio_proxy_config import load_mcp_proxy_config
from app.mcp_stdio_proxy_runtime import run_mcp_stdio_proxy
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop
from core.runtime.opencl_environment import configure_opencl_runtime_environment

__all__ = ("main",)


async def _run() -> int:
    config = load_mcp_proxy_config()
    return await run_mcp_stdio_proxy(config)


def main() -> None:
    configure_opencl_runtime_environment()
    try:
        raise SystemExit(run_coroutine_in_new_event_loop(_run()))
    except KeyboardInterrupt as exception:
        raise SystemExit(0) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        sys.stderr.write(f"{exception}\n")
        raise SystemExit(1) from exception


if __name__ == "__main__":
    main()
