"""SoAI - Shared logging formatter support primitives [backend/core/logging/formatter_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import re

from core.errors.trace_logging import TRACE_LEVEL

__all__ = (
    "ANSI_CODE_PATTERN",
    "ANSI_RESET",
    "ROOT_LOGGER_NAME",
    "normalize_component_name",
    "normalize_compression_suffix",
    "resolve_log_level",
    "strip_ansi_codes",
)

ROOT_LOGGER_NAME = "SoAI"
ANSI_RESET = "\x1b[0m"
ANSI_CODE_PATTERN = "\\x1b\\[[0-9;]*m"


def _normalize_acronym_token(token: str) -> str:
    match token:
        case "Soai":
            return ROOT_LOGGER_NAME
        case "Acl":
            return "ACL"
        case "Amd":
            return "AMD"
        case "Api":
            return "API"
        case "Cpu":
            return "CPU"
        case "Db":
            return "DB"
        case "Dns":
            return "DNS"
        case "Gpu":
            return "GPU"
        case "Http":
            return "HTTP"
        case "Id":
            return "ID"
        case "Io":
            return "IO"
        case "Ipc":
            return "IPC"
        case "Json":
            return "JSON"
        case "Mcp":
            return "MCP"
        case "Nvml":
            return "NVML"
        case "Pty":
            return "PTY"
        case "Rag":
            return "RAG"
        case "Sdk":
            return "SDK"
        case "Smi":
            return "SMI"
        case "Sql":
            return "SQL"
        case "Ssh":
            return "SSH"
        case "Sse":
            return "SSE"
        case "Tls":
            return "TLS"
        case "Ui":
            return "UI"
        case "Url":
            return "URL"
        case _:
            return token


def resolve_log_level(level_name: str) -> int:
    upper_name = (level_name or "INFO").upper()
    if upper_name == "TRACE":
        return TRACE_LEVEL
    match upper_name:
        case "CRITICAL":
            return logging.CRITICAL
        case "ERROR":
            return logging.ERROR
        case "WARNING":
            return logging.WARNING
        case "WARN":
            return logging.WARNING
        case "INFO":
            return logging.INFO
        case "DEBUG":
            return logging.DEBUG
        case "NOTSET":
            return logging.NOTSET
        case _:
            return logging.INFO


def strip_ansi_codes(value: str) -> str:
    return re.sub(ANSI_CODE_PATTERN, "", str(value))


def normalize_component_name(name: str) -> str:
    if not name:
        return ROOT_LOGGER_NAME
    if name == ROOT_LOGGER_NAME:
        return ROOT_LOGGER_NAME
    if name.startswith("[") and name.endswith("]"):
        inner = name[1:-1].strip()
        return _normalize_component_segments(inner) or ROOT_LOGGER_NAME
    prefix = f"{ROOT_LOGGER_NAME}."
    if name.startswith(f"{prefix}Plugin."):
        suffix = name[len(prefix) :]
        return suffix.replace(".", "/").strip() or ROOT_LOGGER_NAME
    if name.startswith(prefix):
        suffix = name[len(prefix) :]
        component = f"{ROOT_LOGGER_NAME}/{suffix.replace('.', '/')}".strip() or ROOT_LOGGER_NAME
        return _normalize_component_segments(component) or ROOT_LOGGER_NAME
    if name.startswith("uvicorn"):
        component = f"{ROOT_LOGGER_NAME}/{name.replace('.', '/')}".strip() or ROOT_LOGGER_NAME
        return _normalize_component_segments(component) or ROOT_LOGGER_NAME
    component = f"{ROOT_LOGGER_NAME}/{name.replace('.', '/')}".strip() or ROOT_LOGGER_NAME
    return _normalize_component_segments(component) or ROOT_LOGGER_NAME


def _normalize_component_segments(component_name: str) -> str:
    if not component_name:
        return component_name
    component_segments = component_name.split("/")
    normalized_segments: list[str] = []
    for component_segment in component_segments:
        segment_tokens = component_segment.split("_")
        normalized_tokens = [
            _normalize_acronym_token(segment_token.title()) for segment_token in segment_tokens
        ]
        normalized_segments.append("_".join(normalized_tokens))
    return "/".join(normalized_segments)


def normalize_compression_suffix(candidate: str | None) -> str:
    if candidate is None:
        return ".gz"
    suffix_value = str(candidate).strip()
    if not suffix_value or any(sep in suffix_value for sep in ("/", "\\")):
        return ".gz"
    return suffix_value if suffix_value.startswith(".") else f".{suffix_value}"
