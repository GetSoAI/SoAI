"""SoAI - Shared IPC message size settings [backend/core/ipc/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.config.byte_sizes import GIB_BYTES, MIB_BYTES
from core.config.integer_requirements import require_config_int_between
from core.errors.exceptions import ConfigurationError
from core.ipc.ndjson import NdjsonCodec

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "IPC_MAX_MESSAGE_BYTES_CONFIG_KEY",
    "IPC_MAX_MESSAGE_BYTES_ENV_KEY",
    "build_ndjson_codec_from_env",
    "resolve_ipc_max_message_bytes",
    "resolve_ipc_max_message_bytes_from_env",
)

IPC_MAX_MESSAGE_BYTES_CONFIG_KEY = "SYSTEM.IPC.MAX_MESSAGE_BYTES"
IPC_MAX_MESSAGE_BYTES_ENV_KEY = "SOAI_IPC_MAX_MESSAGE_BYTES"
IPC_MIN_MESSAGE_BYTES = MIB_BYTES
IPC_MAX_MESSAGE_BYTES = GIB_BYTES


def resolve_ipc_max_message_bytes(config: ConfigProtocol) -> int:
    return require_config_int_between(
        config.get_int(IPC_MAX_MESSAGE_BYTES_CONFIG_KEY),
        key=IPC_MAX_MESSAGE_BYTES_CONFIG_KEY,
        minimum=IPC_MIN_MESSAGE_BYTES,
        maximum=IPC_MAX_MESSAGE_BYTES,
    )


def resolve_ipc_max_message_bytes_from_env() -> int:
    raw_value = str(os.environ.get(IPC_MAX_MESSAGE_BYTES_ENV_KEY, "")).strip()
    if not raw_value:
        return NdjsonCodec.default_max_line_bytes()
    try:
        parsed_value = int(raw_value)
    except ValueError as exception:
        raise ConfigurationError(
            f"{IPC_MAX_MESSAGE_BYTES_ENV_KEY} must be an integer.",
        ) from exception
    return require_config_int_between(
        parsed_value,
        key=IPC_MAX_MESSAGE_BYTES_ENV_KEY,
        minimum=IPC_MIN_MESSAGE_BYTES,
        maximum=IPC_MAX_MESSAGE_BYTES,
    )


def build_ndjson_codec_from_env() -> NdjsonCodec:
    return NdjsonCodec(max_line_bytes=resolve_ipc_max_message_bytes_from_env())
