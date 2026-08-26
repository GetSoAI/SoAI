"""SoAI - Shared SoAI and user system prompt injection [backend/features/agent/runtime/system_prompt_injection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.prompt_injection_messages import prune_injected_prompt_messages
from core.conversations.conversation_model_settings_resolution import (
    resolve_optional_conversation_model_settings,
)
from core.conversations.conversation_settings_resolution import (
    read_authoritative_chat_settings,
    resolve_chat_settings,
)
from core.errors.exceptions import StateError, ValidationError
from core.model_settings.normalization import (
    extract_agent_mode,
    read_optional_agent_settings,
)
from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.openai.internal_message_metadata import (
    SOAI_PROMPT_PROJECTION_MESSAGE_TYPE,
    SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE,
)
from core.openai.request_fields import resolve_optional_model_name
from core.openai.system_prompt_support import (
    detect_timezone_label,
    insert_system_message,
    read_soai_system_prompt_mode,
    render_identity_display_names,
    resolve_platform_label,
    should_inject_soai_system_prompt,
    strip_injected_soai_messages,
)
from core.prompts.system_prompts import (
    render_soai_system_prompt_v1,
    render_text_prompt_template_v1,
)
from core.runtime.request_sources import (
    REQUEST_SOURCE_OPENAI,
    REQUEST_SOURCE_WEBUI_WS,
    RequestSource,
    normalize_request_source,
)
from core.timing.formatting import utc_now
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("inject_soai_and_user_system_prompts",)


def _require_request_source(value: RequestSource) -> RequestSource:
    if not isinstance(value, str):
        raise ValidationError("request_source must be a string.")
    try:
        normalized = normalize_request_source(value)
    except ValidationError as exception:
        raise ValidationError(f"Unsupported request_source: {value.strip()}") from exception
    if normalized is None:
        raise ValidationError("request_source must be a non-empty string.")
    return normalized


def _extract_explicit_agent_mode(model_settings: JSONDict | None) -> str | None:
    if model_settings is None:
        return None
    agent_settings = read_optional_agent_settings(model_settings)
    if "mode" not in agent_settings:
        return None
    return extract_agent_mode(model_settings, strict=False)


async def inject_soai_and_user_system_prompts(
    *,
    config: ConfigProtocol,
    database_conversations: DatabaseConversationsProtocol | None,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol | None,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol | None,
    request_json: JSONDict,
    user_id: int,
    request_source: RequestSource,
    tools_visible_to_model: bool,
    model_settings_snapshot: JSONDict | None = None,
) -> None:
    request_source = _require_request_source(request_source)
    if request_source == REQUEST_SOURCE_OPENAI:
        return
    config_mode = read_soai_system_prompt_mode(config)
    raw_messages = request_json.get("messages")
    if not isinstance(raw_messages, list):
        return
    messages: list[JSONDict] = []
    for index, item in enumerate(raw_messages):
        message = coerce_json_dict(item)
        if message is None:
            raise ValidationError(
                f"Message at index {index} must be an object.",
                details={"param": f"messages[{index}]"},
            )
        messages.append(message)
    request_json["messages"] = messages
    model_id = resolve_optional_model_name(request_json)
    conv_value = request_json.get("conv_id")
    conv_id = conv_value.strip() if isinstance(conv_value, str) and conv_value.strip() else None
    conversation_settings = (
        dict(model_settings_snapshot) if model_settings_snapshot is not None else None
    )
    if conversation_settings is not None:
        resolved = read_authoritative_chat_settings(conversation_settings)
    else:
        if database_conversations is None:
            raise StateError("database_conversations is required for SoAI prompt injection.")
        if database_chat_identity_defaults is None:
            raise StateError(
                "database_chat_identity_defaults is required for SoAI prompt injection.",
            )
        if database_chat_model_defaults is None:
            raise StateError(
                "database_chat_model_defaults is required for SoAI prompt injection.",
            )
        if conv_id and user_id > 0:
            record = await database_conversations.get_conversation(conv_id, user_id)
            if isinstance(record, dict):
                conversation_settings = resolve_optional_conversation_model_settings(
                    record.get("model_settings"),
                )
        resolved = await resolve_chat_settings(
            user_id=user_id,
            model_id=model_id,
            conversation_model_settings=conversation_settings,
            database_chat_identity_defaults=database_chat_identity_defaults,
            database_chat_model_defaults=database_chat_model_defaults,
        )
    try:
        request_agent_mode = _extract_explicit_agent_mode(request_json)
    except ValidationError as error:
        raise StateError(error.message) from error
    try:
        conversation_agent_mode = _extract_explicit_agent_mode(conversation_settings)
    except ValidationError as error:
        raise StateError(error.message) from error
    agent_mode = request_agent_mode or conversation_agent_mode or "chat"
    if agent_mode == "chat":
        prune_injected_prompt_messages(messages)
    strip_injected_soai_messages(messages)
    soai_enabled = should_inject_soai_system_prompt(
        config_mode=config_mode,
        request_source=request_source,
        conversation_toggle_enabled=bool(resolved.prompts.soai_system_prompt_enabled),
    )
    assistant_name = coerce_optional_trimmed_str(resolved.identity.assistant_display_name)
    user_name = coerce_optional_trimmed_str(resolved.identity.user_display_name)
    leading_system_texts: list[str] = []
    leading_end_index = 0
    for index, candidate in enumerate(messages):
        role = candidate.get("role")
        if role in OPENAI_PINNED_ROLES:
            leading_end_index = index + 1
            continue
        break
    for leading_message in messages[:leading_end_index]:
        role = leading_message.get("role")
        if role not in OPENAI_PINNED_ROLES:
            continue
        content = leading_message.get("content")
        if isinstance(content, str) and content.strip():
            leading_system_texts.append(content.strip())
    if leading_end_index > 0:
        messages[:] = list(messages[leading_end_index:])
    injected_fragments: list[str] = []
    if soai_enabled:
        rendered = render_soai_system_prompt_v1(
            platform_info=resolve_platform_label(),
            user_name=user_name or "",
            assistant_name=assistant_name or "",
            agent_mode=agent_mode,
            tools_visible_to_model=tools_visible_to_model,
            request_source=request_source,
        ).strip()
        if rendered:
            injected_fragments.append(rendered)
    elif request_source == REQUEST_SOURCE_WEBUI_WS:
        identity_message = render_identity_display_names(
            user_name=user_name,
            assistant_name=assistant_name,
        )
        if isinstance(identity_message, str) and identity_message.strip():
            injected_fragments.append(identity_message.strip())
    injected_fragments.extend(leading_system_texts)
    user_system_prompt = resolved.prompts.user_system_prompt
    if isinstance(user_system_prompt, str) and user_system_prompt.strip():
        user_prompt_text = user_system_prompt.strip()
        if user_prompt_text not in injected_fragments:
            injected_fragments.append(user_prompt_text)
    if injected_fragments:
        insert_system_message(
            messages,
            "\n\n".join(injected_fragments).strip(),
            index=0,
            message_type=SOAI_PROMPT_PROJECTION_MESSAGE_TYPE,
        )
    if soai_enabled:
        _insert_runtime_context_system_message(messages)
    request_json["messages"] = messages


def _insert_runtime_context_system_message(messages: list[JSONDict]) -> None:
    now = utc_now().astimezone()
    runtime_context = render_text_prompt_template_v1(
        "soai.runtime_context.v1",
        {
            "SOAI_LOCAL_DATETIME": now.isoformat(timespec="seconds"),
            "SOAI_TIMEZONE": detect_timezone_label(now),
        },
    ).strip()
    if not runtime_context:
        return
    if messages and messages[-1].get("role") != "system":
        insert_system_message(
            messages,
            runtime_context,
            index=len(messages) - 1,
            message_type=SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE,
        )
        return
    insert_system_message(
        messages,
        runtime_context,
        index=len(messages),
        message_type=SOAI_RUNTIME_CONTEXT_MESSAGE_TYPE,
    )
