"""SoAI - Private streamed provider error diagnostics [backend/core/openai/stream_error_diagnostics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors.error_types import ErrorType
from core.security.response_redaction import redact_response_payload
from core.security.sensitive_detection import looks_like_sensitive_string
from core.serialization.json import serialize_json_compact_stable_strict

__all__ = ("StreamErrorDiagnostic",)

_SAFE_PARAMETERS = frozenset(
    {
        "messages",
        "model",
        "max_tokens",
        "max_completion_tokens",
        "response_format",
        "tools",
        "tool_choice",
    }
)


def _safe_symbol(value: str | None, allowed: frozenset[str]) -> str | None:
    normalized = value.strip() if isinstance(value, str) else ""
    if normalized not in allowed or looks_like_sensitive_string(normalized):
        return None
    return normalized


def _safe_trusted_identifier(value: str | None) -> str | None:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized or len(normalized) > 128 or looks_like_sensitive_string(normalized):
        return None
    if re.fullmatch(r"[A-Za-z0-9_.:-]+", normalized) is None:
        return None
    return normalized


@dataclass(frozen=True, slots=True)
class StreamErrorDiagnostic:
    category: str
    source: str
    upstream_type: str | None
    upstream_code: str | None
    upstream_param: str | None
    provider_id: str | None
    operation: str
    task_id: str | None
    trace_id: str | None
    mapped_status: int
    omitted: bool
    requested_tokens: int | None = None
    available_tokens: int | None = None
    missing_capabilities: tuple[str, ...] = ()
    missing_modalities: tuple[str, ...] = ()

    @classmethod
    def from_error(
        cls,
        *,
        category: str,
        source: str,
        upstream_type: str | None,
        upstream_code: str | None,
        upstream_param: str | None,
        provider_id: str | None,
        operation: str,
        task_id: str | None,
        trace_id: str | None,
        mapped_status: int,
        requested_tokens: int | None = None,
        available_tokens: int | None = None,
        missing_capabilities: tuple[str, ...] = (),
        missing_modalities: tuple[str, ...] = (),
        provider_prose_omitted: bool = True,
    ) -> StreamErrorDiagnostic:
        recognized_symbols = frozenset(member.value for member in ErrorType) | frozenset(
            {"BadRequestError", "context_length_exceeded"}
        )
        recognized_type = _safe_symbol(upstream_type, recognized_symbols)
        recognized_code = _safe_symbol(upstream_code, recognized_symbols)
        recognized_param = _safe_symbol(upstream_param, _SAFE_PARAMETERS)
        return cls(
            category=category,
            source=source,
            upstream_type=recognized_type,
            upstream_code=recognized_code,
            upstream_param=recognized_param,
            provider_id=_safe_trusted_identifier(provider_id),
            operation=operation,
            task_id=_safe_trusted_identifier(task_id),
            trace_id=_safe_trusted_identifier(trace_id),
            mapped_status=mapped_status,
            requested_tokens=requested_tokens,
            available_tokens=available_tokens,
            missing_capabilities=tuple(
                symbol for symbol in missing_capabilities if not looks_like_sensitive_string(symbol)
            ),
            missing_modalities=tuple(
                symbol for symbol in missing_modalities if not looks_like_sensitive_string(symbol)
            ),
            omitted=(
                provider_prose_omitted
                or (bool(upstream_type) and recognized_type is None)
                or (bool(upstream_code) and recognized_code is None)
                or (bool(upstream_param) and recognized_param is None)
            ),
        )

    def render(self) -> str:
        summary = serialize_json_compact_stable_strict(
            redact_response_payload(
                {
                    "category": self.category,
                    "source": self.source,
                    "upstream_type": self.upstream_type,
                    "upstream_code": self.upstream_code,
                    "upstream_param": self.upstream_param,
                    "provider_id": self.provider_id,
                    "operation": self.operation,
                    "task_id": self.task_id,
                    "trace_id": self.trace_id,
                    "mapped_status": self.mapped_status,
                    "omitted": self.omitted,
                    "truncated": False,
                    "requested_tokens": self.requested_tokens,
                    "available_tokens": self.available_tokens,
                    "missing_capabilities": list(self.missing_capabilities),
                    "missing_modalities": list(self.missing_modalities),
                }
            ),
        )
        if len(summary) > 512:
            return serialize_json_compact_stable_strict(
                {
                    "category": self.category,
                    "source": self.source,
                    "mapped_status": self.mapped_status,
                    "omitted": True,
                    "truncated": True,
                },
            )
        return summary
