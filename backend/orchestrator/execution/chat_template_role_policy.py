"""SoAI - Adaptive chat template role policy resolution [backend/orchestrator/execution/chat_template_role_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx2

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import IpcRemoteRequestError
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_error_responses import extract_http_response_message
from core.openai.chat_template_role_policy import (
    CHAT_TEMPLATE_ROLE_POLICY_AUTO,
    CHAT_TEMPLATE_ROLE_POLICY_SEQUENCE,
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY,
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY,
    SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
    is_chat_template_role_error_message,
    normalize_chat_template_role_policy,
    normalize_chat_template_role_policy_value,
    read_message_compatibility_mode,
)
from core.types.json_value import copy_json_dict

if TYPE_CHECKING:
    from core.models.model_context import ModelContext
    from core.types.json import JSONDict

__all__ = (
    "ChatTemplateRolePolicyCandidate",
    "ChatTemplateRolePolicyResolver",
    "ChatTemplateRolePolicyResolverDependencies",
    "is_chat_template_role_policy_rejection",
)

_CONFIG_KEY = "API.OPENAI.PROMPTS.MESSAGE_COMPATIBILITY_MODE"


@dataclass(frozen=True, slots=True)
class ChatTemplateRolePolicyResolverDependencies:
    config: ConfigProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ChatTemplateRolePolicyResolverDependencies",
            config=self.config,
        )


@dataclass(frozen=True, slots=True)
class ChatTemplateRolePolicyCandidate:
    policy: str
    payload: JSONDict
    cacheable: bool


@dataclass(slots=True)
class ChatTemplateRolePolicyResolver:
    deps: ChatTemplateRolePolicyResolverDependencies
    _cache: dict[str, str] = field(default_factory=dict[str, str])
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def build_candidate_payloads(
        self,
        payload: JSONDict,
        model_context: ModelContext,
    ) -> list[ChatTemplateRolePolicyCandidate]:
        explicit_policy = _resolve_explicit_policy(payload, model_context.parameters)
        if explicit_policy is not None and explicit_policy != CHAT_TEMPLATE_ROLE_POLICY_AUTO:
            return [
                ChatTemplateRolePolicyCandidate(
                    policy=explicit_policy,
                    payload=_with_policy(payload, explicit_policy),
                    cacheable=False,
                ),
            ]
        mode = read_message_compatibility_mode(self.deps.config.get_str(_CONFIG_KEY))
        if mode != CHAT_TEMPLATE_ROLE_POLICY_AUTO:
            return [
                ChatTemplateRolePolicyCandidate(
                    policy=mode,
                    payload=_with_policy(payload, mode),
                    cacheable=False,
                ),
            ]
        key = _cache_key(model_context)
        async with self._lock:
            cached = self._cache.get(key)
        candidates = list(CHAT_TEMPLATE_ROLE_POLICY_SEQUENCE)
        if cached in candidates:
            candidates.remove(cached)
            candidates.insert(0, cached)
        return [
            ChatTemplateRolePolicyCandidate(
                policy=candidate,
                payload=_with_policy(payload, candidate),
                cacheable=True,
            )
            for candidate in candidates
        ]

    async def record_success(self, model_context: ModelContext, policy: str) -> None:
        normalized = normalize_chat_template_role_policy(policy)
        if normalized == CHAT_TEMPLATE_ROLE_POLICY_AUTO:
            return
        async with self._lock:
            self._cache[_cache_key(model_context)] = normalized


def is_chat_template_role_policy_rejection(exception: Exception) -> bool:
    if isinstance(exception, httpx2.HTTPStatusError):
        return _is_chat_template_role_policy_http_error(exception)
    if isinstance(exception, ExternalServiceError | IpcRemoteRequestError):
        return _is_chat_template_role_policy_soai_error(exception)
    return False


def _is_chat_template_role_policy_http_error(exception: httpx2.HTTPStatusError) -> bool:
    response = exception.response
    if response is None:
        return False
    status_code = response.status_code
    if status_code < 400:
        return False
    message = extract_http_response_message(response, status_code)
    return is_chat_template_role_error_message(message)


def _is_chat_template_role_policy_soai_error(
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> bool:
    if is_chat_template_role_error_message(exception.message):
        return True
    details = exception.details
    if not isinstance(details, dict):
        return False
    if (
        details.get(CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY)
        == CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY
    ):
        return True
    for value in details.values():
        if isinstance(value, str) and is_chat_template_role_error_message(value):
            return True
    return False


def _with_policy(payload: JSONDict, policy: str) -> JSONDict:
    copied = copy_json_dict(payload)
    copied[SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER] = policy
    return copied


def _resolve_explicit_policy(payload: JSONDict, parameters: JSONDict) -> str | None:
    if SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER in payload:
        return normalize_chat_template_role_policy_value(
            payload.get(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER),
            label=SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
        )
    if SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER in parameters:
        return normalize_chat_template_role_policy_value(
            parameters.get(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER),
            label=SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
        )
    return None


def _cache_key(model_context: ModelContext) -> str:
    provider_details = model_context.provider_details
    provider_id = ""
    if isinstance(provider_details, dict):
        provider_value = provider_details.get("provider_id")
        provider_id = provider_value.strip() if isinstance(provider_value, str) else ""
    return "\n".join(
        (
            model_context.plugin,
            model_context.source_model_id,
            provider_id,
        ),
    )
