"""SoAI - OpenAI capability evidence resolution from provider model metadata [backend/core/openai/capability_evidence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING

from core.openai.capability_taxonomy import (
    OPENAI_FEATURE_MATRIX,
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIModality,
)
from core.openai.effective_profile import OPENAI_MODALITY_CHAT_FEATURE_LINKS

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OPENAI_CAPABILITY_EVIDENCE_KEY",
    "OpenAICapabilityEvidenceSource",
    "OpenAICapabilityEvidenceStatus",
    "build_openai_model_capability_profile",
    "normalize_openai_capability_evidence",
)

OPENAI_CAPABILITY_EVIDENCE_KEY = "openai_capability_evidence"
_MODALITIES_CATEGORY = "modalities"
_CHAT_FEATURES_CATEGORY = "chat_features"
_ENDPOINTS_CATEGORY = "endpoints"


class OpenAICapabilityEvidenceStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class OpenAICapabilityEvidenceSource(str, Enum):
    EXPLICIT = "explicit"
    PROVIDER_CAPABILITY = "provider_capability"
    MODALITY = "modality"
    SUPPORTED_PARAMETERS = "supported_parameters"
    DEFAULT = "default"


_COMPATIBILITY_DEFAULTS: frozenset[tuple[str, str]] = frozenset(
    {
        (_ENDPOINTS_CATEGORY, OpenAIEndpoint.CHAT_COMPLETIONS.value),
        (_CHAT_FEATURES_CATEGORY, OpenAIChatFeature.TOOL_CALLING.value),
        (_CHAT_FEATURES_CATEGORY, OpenAIChatFeature.PARALLEL_TOOL_CALLS.value),
        (_CHAT_FEATURES_CATEGORY, OpenAIChatFeature.STRUCTURED_OUTPUT.value),
        (_CHAT_FEATURES_CATEGORY, OpenAIChatFeature.JSON_SCHEMA.value),
    }
)
_PROVIDER_CAPABILITY_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("completion_chat", _ENDPOINTS_CATEGORY, OpenAIEndpoint.CHAT_COMPLETIONS.value),
    ("function_calling", _CHAT_FEATURES_CATEGORY, OpenAIChatFeature.TOOL_CALLING.value),
    ("vision", _CHAT_FEATURES_CATEGORY, OpenAIChatFeature.VISION.value),
)
_PARAMETER_EVIDENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (OpenAIChatFeature.TOOL_CALLING.value, ("tools", "tool_choice")),
    (OpenAIChatFeature.PARALLEL_TOOL_CALLS.value, ("parallel_tool_calls",)),
    (
        OpenAIChatFeature.STRUCTURED_OUTPUT.value,
        ("response_format", "structured_outputs", "structured_output"),
    ),
    (
        OpenAIChatFeature.JSON_SCHEMA.value,
        ("json_schema", "response_format_json_schema", "structured_outputs"),
    ),
)
_IMAGE_MODALITY_ALIAS = "image"


@dataclass(slots=True)
class _Evidence:
    status: OpenAICapabilityEvidenceStatus
    source: OpenAICapabilityEvidenceSource


def _source_strength(source: OpenAICapabilityEvidenceSource) -> int:
    match source:
        case OpenAICapabilityEvidenceSource.EXPLICIT:
            return 3
        case OpenAICapabilityEvidenceSource.PROVIDER_CAPABILITY:
            return 2
        case (
            OpenAICapabilityEvidenceSource.MODALITY
            | OpenAICapabilityEvidenceSource.SUPPORTED_PARAMETERS
        ):
            return 1
        case _:
            return 0


@cache
def _capability_tokens() -> Mapping[str, tuple[str, ...]]:
    tokens = {
        category: tuple(token for token, _flag in entries)
        for category, entries in OPENAI_FEATURE_MATRIX
    }
    tokens[_MODALITIES_CATEGORY] = tuple(modality.value for modality in OpenAIModality)
    return tokens


def _record(
    evidence: dict[str, dict[str, _Evidence]],
    category: str,
    token: str,
    supported: bool,
    source: OpenAICapabilityEvidenceSource,
) -> None:
    category_evidence = evidence.get(category)
    if category_evidence is None or token not in category_evidence:
        return
    current = category_evidence[token]
    if _source_strength(source) <= _source_strength(current.source):
        return
    category_evidence[token] = _Evidence(
        (
            OpenAICapabilityEvidenceStatus.SUPPORTED
            if supported
            else OpenAICapabilityEvidenceStatus.UNSUPPORTED
        ),
        source,
    )


def _reported_modalities(model_def: Mapping[str, JSONValue]) -> list[str] | None:
    value = model_def.get("modalities")
    architecture = model_def.get("architecture")
    if not isinstance(value, list) and isinstance(architecture, Mapping):
        value = architecture.get("input_modalities")
    if not isinstance(value, list):
        return None
    reported: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        normalized = entry.strip().lower()
        if normalized == _IMAGE_MODALITY_ALIAS:
            normalized = OpenAIModality.VISION.value
        if normalized in _capability_tokens()[_MODALITIES_CATEGORY] and normalized not in reported:
            reported.append(normalized)
    return reported or None


def _apply_modality_evidence(
    evidence: dict[str, dict[str, _Evidence]],
    reported_modalities: list[str] | None,
) -> None:
    if reported_modalities is None:
        return
    source = OpenAICapabilityEvidenceSource.MODALITY
    for modality in _capability_tokens()[_MODALITIES_CATEGORY]:
        _record(
            evidence,
            _MODALITIES_CATEGORY,
            modality,
            modality in reported_modalities,
            source,
        )
    for modality, feature in OPENAI_MODALITY_CHAT_FEATURE_LINKS:
        _record(
            evidence,
            _CHAT_FEATURES_CATEGORY,
            feature,
            modality in reported_modalities,
            source,
        )


def _apply_explicit_evidence(
    evidence: dict[str, dict[str, _Evidence]],
    reported: JSONValue,
) -> None:
    if not isinstance(reported, Mapping):
        return
    for category, features in reported.items():
        if not isinstance(category, str) or not isinstance(features, Mapping):
            continue
        for token, supported in features.items():
            if isinstance(token, str) and isinstance(supported, bool):
                _record(
                    evidence,
                    category,
                    token,
                    supported,
                    OpenAICapabilityEvidenceSource.EXPLICIT,
                )


def _apply_provider_evidence(
    evidence: dict[str, dict[str, _Evidence]],
    reported: JSONValue,
) -> None:
    if not isinstance(reported, Mapping):
        return
    for field_name, category, token in _PROVIDER_CAPABILITY_FIELDS:
        supported = reported.get(field_name)
        if isinstance(supported, bool):
            _record(
                evidence,
                category,
                token,
                supported,
                OpenAICapabilityEvidenceSource.PROVIDER_CAPABILITY,
            )


def _apply_parameter_evidence(
    evidence: dict[str, dict[str, _Evidence]],
    reported: JSONValue,
) -> None:
    if not isinstance(reported, list):
        return
    names = {
        entry.strip().lower() for entry in reported if isinstance(entry, str) and entry.strip()
    }
    for token, parameter_names in _PARAMETER_EVIDENCE:
        _record(
            evidence,
            _CHAT_FEATURES_CATEGORY,
            token,
            any(name in names for name in parameter_names),
            OpenAICapabilityEvidenceSource.SUPPORTED_PARAMETERS,
        )


def _apply_feature_modality_links(evidence: dict[str, dict[str, _Evidence]]) -> None:
    for modality, feature in OPENAI_MODALITY_CHAT_FEATURE_LINKS:
        feature_evidence = evidence[_CHAT_FEATURES_CATEGORY][feature]
        if feature_evidence.status is OpenAICapabilityEvidenceStatus.SUPPORTED:
            _record(evidence, _MODALITIES_CATEGORY, modality, True, feature_evidence.source)


def _is_enabled(category: str, token: str, entry: _Evidence) -> bool:
    if entry.status is OpenAICapabilityEvidenceStatus.UNKNOWN:
        return (category, token) in _COMPATIBILITY_DEFAULTS or (
            category == _MODALITIES_CATEGORY and token == OpenAIModality.TEXT.value
        )
    return entry.status is OpenAICapabilityEvidenceStatus.SUPPORTED


def build_openai_model_capability_profile(
    model_def: Mapping[str, JSONValue],
) -> JSONDict:
    unknown = OpenAICapabilityEvidenceStatus.UNKNOWN
    default = OpenAICapabilityEvidenceSource.DEFAULT
    evidence = {
        category: {token: _Evidence(unknown, default) for token in tokens}
        for category, tokens in _capability_tokens().items()
    }
    _apply_explicit_evidence(evidence, model_def.get("openai_capabilities"))
    _apply_provider_evidence(evidence, model_def.get("capabilities"))
    _apply_modality_evidence(evidence, _reported_modalities(model_def))
    _apply_parameter_evidence(evidence, model_def.get("supported_parameters"))
    _apply_feature_modality_links(evidence)
    modalities = [
        token
        for token, entry in evidence[_MODALITIES_CATEGORY].items()
        if _is_enabled(_MODALITIES_CATEGORY, token, entry)
    ] or [OpenAIModality.TEXT.value]
    capabilities: JSONDict = {"modalities": list(modalities)}
    evidence_payload: JSONDict = {}
    for category, entries in evidence.items():
        evidence_payload[category] = {
            token: {"status": entry.status.value, "source": entry.source.value}
            for token, entry in entries.items()
        }
        if category == _MODALITIES_CATEGORY:
            continue
        section: JSONDict = {
            token: _is_enabled(category, token, entry) for token, entry in entries.items()
        }
        capabilities[category] = section
        capabilities.update(section)
    return {
        "modalities": modalities,
        "openai_capabilities": capabilities,
        OPENAI_CAPABILITY_EVIDENCE_KEY: evidence_payload,
    }


def _normalize_evidence_entry(entry: Mapping[str, JSONValue]) -> JSONDict | None:
    status = entry.get("status")
    source = entry.get("source")
    if not isinstance(status, str) or not isinstance(source, str):
        return None
    try:
        return {
            "status": OpenAICapabilityEvidenceStatus(status).value,
            "source": OpenAICapabilityEvidenceSource(source).value,
        }
    except ValueError:
        return None


def normalize_openai_capability_evidence(value: JSONValue) -> JSONDict | None:
    if not isinstance(value, Mapping):
        return None
    normalized: JSONDict = {}
    for category, tokens in _capability_tokens().items():
        entries = value.get(category)
        if not isinstance(entries, Mapping):
            continue
        category_payload: JSONDict = {}
        for token in tokens:
            entry = entries.get(token)
            normalized_entry = (
                _normalize_evidence_entry(entry) if isinstance(entry, Mapping) else None
            )
            if normalized_entry is not None:
                category_payload[token] = normalized_entry
        if category_payload:
            normalized[category] = category_payload
    return normalized or None
