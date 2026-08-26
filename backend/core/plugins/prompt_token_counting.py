"""SoAI - Plugin prompt token count result contracts [backend/core/plugins/prompt_token_counting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int
from core.validation.strings import coerce_optional_trimmed_str, coerce_required_non_empty_str

__all__ = (
    "PluginPromptTokenCountResult",
    "build_exact_prompt_token_count_result",
    "build_estimated_prompt_token_count_result",
    "build_unsupported_prompt_token_count_result",
    "parse_plugin_prompt_token_count_result",
)

PLUGIN_PROMPT_TOKEN_PRECISIONS = frozenset({"exact", "estimated", "unsupported"})


@dataclass(frozen=True, slots=True)
class PluginPromptTokenCountResult:
    precision: str
    prompt_tokens: int | None
    source: str
    reason: str | None
    tokenizer_id: str | None


def build_exact_prompt_token_count_result(
    *,
    prompt_tokens: int,
    source: str,
    tokenizer_id: str,
) -> JSONDict:
    if not is_non_negative_strict_int(prompt_tokens):
        raise ValidationError("Exact prompt token count must be a non-negative integer.")
    return {
        "precision": "exact",
        "prompt_tokens": prompt_tokens,
        "source": coerce_required_non_empty_str(source, label="Prompt token count source"),
        "reason": None,
        "tokenizer_id": coerce_required_non_empty_str(
            tokenizer_id,
            label="Prompt token count tokenizer id",
        ),
    }


def build_estimated_prompt_token_count_result(
    *,
    prompt_tokens: int,
    source: str,
    reason: str,
    tokenizer_id: str | None = None,
) -> JSONDict:
    if not is_non_negative_strict_int(prompt_tokens):
        raise ValidationError("Estimated prompt token count must be a non-negative integer.")
    return {
        "precision": "estimated",
        "prompt_tokens": prompt_tokens,
        "source": coerce_required_non_empty_str(source, label="Prompt token count source"),
        "reason": coerce_required_non_empty_str(reason, label="Prompt token count reason"),
        "tokenizer_id": coerce_optional_trimmed_str(tokenizer_id),
    }


def build_unsupported_prompt_token_count_result(*, reason: str) -> JSONDict:
    return {
        "precision": "unsupported",
        "prompt_tokens": None,
        "source": "plugin",
        "reason": coerce_required_non_empty_str(reason, label="Prompt token count reason"),
        "tokenizer_id": None,
    }


def _read_precision(payload: JSONDict) -> str:
    precision = coerce_optional_trimmed_str(payload.get("precision"))
    if precision not in PLUGIN_PROMPT_TOKEN_PRECISIONS:
        raise ValidationError("Plugin prompt token count precision is invalid.")
    return precision


def _read_prompt_tokens(payload: JSONDict, *, precision: str) -> int | None:
    value = payload.get("prompt_tokens")
    if precision == "unsupported":
        if value is not None:
            raise ValidationError("Unsupported prompt token counts must not include tokens.")
        return None
    if not is_non_negative_strict_int(value):
        raise ValidationError("Plugin prompt token count must include non-negative tokens.")
    return value


def parse_plugin_prompt_token_count_result(payload: JSONDict) -> PluginPromptTokenCountResult:
    precision = _read_precision(payload)
    prompt_tokens = _read_prompt_tokens(payload, precision=precision)
    source = coerce_required_non_empty_str(
        payload.get("source"),
        label="Prompt token count source",
    )
    reason = coerce_optional_trimmed_str(payload.get("reason"))
    tokenizer_id = coerce_optional_trimmed_str(payload.get("tokenizer_id"))
    if precision == "exact" and tokenizer_id is None:
        raise ValidationError("Exact prompt token counts require tokenizer_id.")
    if precision != "exact" and reason is None:
        raise ValidationError("Non-exact prompt token counts require a reason.")
    return PluginPromptTokenCountResult(
        precision=precision,
        prompt_tokens=prompt_tokens,
        source=source,
        reason=reason,
        tokenizer_id=tokenizer_id,
    )
