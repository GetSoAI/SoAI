"""SoAI - Conversation identity and prompt settings resolution [backend/core/conversations/conversation_settings_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.model_settings.normalization import (
    normalize_identity_settings,
    normalize_optional_bool_setting,
    normalize_prompt_settings,
)
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "ResolvedChatIdentity",
    "ResolvedChatPrompts",
    "ResolvedChatSettings",
    "apply_resolved_chat_settings",
    "read_authoritative_chat_settings",
    "resolve_chat_settings",
)


@dataclass(frozen=True, slots=True)
class ResolvedChatIdentity:
    user_display_name: str | None
    assistant_display_name: str | None


@dataclass(frozen=True, slots=True)
class ResolvedChatPrompts:
    user_system_prompt: str | None
    soai_system_prompt_enabled: bool


@dataclass(frozen=True, slots=True)
class ResolvedChatSettings:
    identity: ResolvedChatIdentity
    prompts: ResolvedChatPrompts


def read_authoritative_chat_settings(
    conversation_model_settings: JSONDict,
) -> ResolvedChatSettings:
    identity = normalize_identity_settings(conversation_model_settings.get("identity"))
    prompts = normalize_prompt_settings(conversation_model_settings.get("prompts"))
    return ResolvedChatSettings(
        identity=ResolvedChatIdentity(
            user_display_name=coerce_optional_trimmed_str(identity.get("user_display_name")),
            assistant_display_name=coerce_optional_trimmed_str(
                identity.get("assistant_display_name"),
            ),
        ),
        prompts=ResolvedChatPrompts(
            user_system_prompt=coerce_optional_trimmed_str(prompts.get("user_system_prompt")),
            soai_system_prompt_enabled=bool(prompts.get("soai_system_prompt_enabled")),
        ),
    )


def apply_resolved_chat_settings(
    *,
    model_settings: JSONDict,
    resolved: ResolvedChatSettings,
) -> JSONDict:
    normalized_model_settings: JSONDict = dict(model_settings)
    normalized_model_settings["identity"] = normalize_identity_settings(
        {
            "user_display_name": resolved.identity.user_display_name,
            "assistant_display_name": resolved.identity.assistant_display_name,
        },
    )
    normalized_model_settings["prompts"] = normalize_prompt_settings(
        {
            "user_system_prompt": resolved.prompts.user_system_prompt,
            "soai_system_prompt_enabled": resolved.prompts.soai_system_prompt_enabled,
        },
    )
    return normalized_model_settings


async def resolve_chat_settings(
    *,
    user_id: int,
    model_id: str | None,
    conversation_model_settings: JSONDict | None,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
) -> ResolvedChatSettings:
    conversation_model_settings = conversation_model_settings or {}
    identity_dict = coerce_json_dict(conversation_model_settings.get("identity"))
    prompts_dict = coerce_json_dict(conversation_model_settings.get("prompts"))
    identity_raw = normalize_identity_settings(identity_dict)
    prompts_raw = normalize_prompt_settings(prompts_dict)
    identity_has_user_display_name = (
        identity_dict is not None and "user_display_name" in identity_dict
    )
    identity_has_assistant_display_name = (
        identity_dict is not None and "assistant_display_name" in identity_dict
    )
    prompts_has_user_system_prompt = (
        prompts_dict is not None and "user_system_prompt" in prompts_dict
    )
    prompts_has_soai_enabled = (
        prompts_dict is not None and "soai_system_prompt_enabled" in prompts_dict
    )
    identity_defaults = (
        await database_chat_identity_defaults.get_identity_defaults(user_id)
        if user_id > 0
        else None
    )
    user_default_display_name = coerce_optional_trimmed_str(
        (identity_defaults or {}).get("user_display_name"),
    )
    model_defaults: JSONDict | None = None
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if user_id > 0 and normalized_model_id is not None:
        model_defaults = await database_chat_model_defaults.get_model_defaults(
            user_id,
            normalized_model_id,
        )
    model_default_assistant = coerce_optional_trimmed_str(
        (model_defaults or {}).get("assistant_display_name"),
    )
    model_default_user_prompt = (model_defaults or {}).get("user_system_prompt")
    model_default_user_prompt = (
        model_default_user_prompt if isinstance(model_default_user_prompt, str) else None
    )
    model_default_user_prompt = (
        model_default_user_prompt
        if model_default_user_prompt and model_default_user_prompt.strip()
        else None
    )
    model_default_soai_enabled = normalize_optional_bool_setting(
        (model_defaults or {}).get("soai_system_prompt_enabled"),
        default=True,
    )
    user_display_name = (
        coerce_optional_trimmed_str(identity_raw.get("user_display_name"))
        if identity_has_user_display_name
        else user_default_display_name
    )
    assistant_display_name = (
        coerce_optional_trimmed_str(identity_raw.get("assistant_display_name"))
        if identity_has_assistant_display_name
        else model_default_assistant
    )
    user_system_prompt_candidate = (
        prompts_raw.get("user_system_prompt")
        if prompts_has_user_system_prompt
        else model_default_user_prompt
    )
    user_system_prompt = (
        user_system_prompt_candidate
        if isinstance(user_system_prompt_candidate, str) and user_system_prompt_candidate.strip()
        else None
    )
    soai_system_prompt_enabled = (
        bool(prompts_raw.get("soai_system_prompt_enabled"))
        if prompts_has_soai_enabled
        else bool(model_default_soai_enabled)
    )
    return ResolvedChatSettings(
        identity=ResolvedChatIdentity(
            user_display_name=user_display_name,
            assistant_display_name=assistant_display_name,
        ),
        prompts=ResolvedChatPrompts(
            user_system_prompt=user_system_prompt,
            soai_system_prompt_enabled=soai_system_prompt_enabled,
        ),
    )
