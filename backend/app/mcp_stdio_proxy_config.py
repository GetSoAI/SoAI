"""SoAI - MCP stdio proxy configuration [backend/app/mcp_stdio_proxy_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.network.urls import build_host_port_url
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.validation.requirements import require_positive_int

__all__ = (
    "McpProxyConfig",
    "load_mcp_proxy_config",
)

LOGGER_NAME = "SoAI.app.mcp_stdio_proxy_config"


@dataclass(frozen=True, slots=True)
class McpProxyConfig:
    endpoint: str
    token: str
    expected_user_id: int
    max_inflight: int
    stdout_queue_size: int
    stdin_queue_size: int


def _read_required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Missing required environment variable: {name}")
    return value.strip()


def load_mcp_proxy_config() -> McpProxyConfig:
    raw_endpoint = os.environ.get("SOAI_MCP_ENDPOINT", "").strip()
    if not raw_endpoint:
        expected_edition = _read_required_env("SOAI_MCP_EDITION")
        if expected_edition not in {"soai-core", "soai-os"}:
            raise ValidationError("SOAI_MCP_EDITION is invalid")
        base_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        runtime_record = read_verified_runtime_instance_record(
            resolve_runtime_record_path(
                base_dir,
                logger=get_logger(LOGGER_NAME),
            ),
            base_dir=base_dir,
            expected_edition=expected_edition,
        )
        if runtime_record is None or runtime_record.api_endpoint is None:
            raise ValidationError("The running SoAI instance has not published an MCP endpoint.")
        runtime_api_endpoint = runtime_record.api_endpoint
        api_base_url = build_host_port_url(
            runtime_api_endpoint.scheme,
            runtime_api_endpoint.local_connect_host,
            runtime_api_endpoint.effective_port,
        )
        raw_endpoint = f"{api_base_url}/mcp"
    token = _read_required_env("SOAI_MCP_TOKEN")
    expected_user_id = require_positive_int(
        _read_required_env("SOAI_MCP_USER_ID"),
        name="SOAI_MCP_USER_ID",
    )
    max_inflight_raw = os.environ.get("SOAI_MCP_MAX_INFLIGHT", "16").strip()
    stdout_queue_raw = os.environ.get("SOAI_MCP_STDOUT_QUEUE_SIZE", "256").strip()
    max_inflight = require_positive_int(max_inflight_raw, name="SOAI_MCP_MAX_INFLIGHT")
    stdout_queue_size = require_positive_int(stdout_queue_raw, name="SOAI_MCP_STDOUT_QUEUE_SIZE")
    stdin_queue_default = str(max_inflight * 32)
    stdin_queue_raw = os.environ.get("SOAI_MCP_STDIN_QUEUE_SIZE", stdin_queue_default).strip()
    stdin_queue_size = require_positive_int(stdin_queue_raw, name="SOAI_MCP_STDIN_QUEUE_SIZE")
    endpoint = raw_endpoint.rstrip("/")
    return McpProxyConfig(
        endpoint=endpoint,
        token=token,
        expected_user_id=expected_user_id,
        max_inflight=max_inflight,
        stdout_queue_size=stdout_queue_size,
        stdin_queue_size=stdin_queue_size,
    )
