"""SoAI - Safe localized Messaging interaction prompts [backend/core/messaging/interaction_prompt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.messaging.response_catalog import format_messaging_response_text
from core.types.json import JSONDict, JSONValue

__all__ = ("render_messaging_interaction_prompt",)

MAX_REMOTE_TOOL_NAME_LENGTH = 80
MAX_REMOTE_QUESTION_LENGTH = 500
MAX_REMOTE_OPTION_LENGTH = 120
MAX_REMOTE_INTERACTION_PROMPT_LENGTH = 1800


def _bounded_text(value: JSONValue, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _render_questions(metadata: JSONDict) -> tuple[str, bool]:
    questions_value = metadata.get("questions")
    if not isinstance(questions_value, list) or not questions_value:
        raise StateError("Messaging ask_user task questions are invalid.")
    rendered: list[str] = []
    contains_secret = False
    for question_index, question_value in enumerate(questions_value, start=1):
        if not isinstance(question_value, dict):
            raise StateError("Messaging ask_user question is invalid.")
        contains_secret = contains_secret or question_value.get("isSecret") is True
        question = _bounded_text(question_value.get("question"), MAX_REMOTE_QUESTION_LENGTH)
        if not question:
            raise StateError("Messaging ask_user question text is invalid.")
        rendered.append(f"{question_index}. {question}")
        options_value = question_value.get("options")
        if isinstance(options_value, list):
            for option_index, option_value in enumerate(options_value, start=1):
                if not isinstance(option_value, dict):
                    continue
                label = _bounded_text(option_value.get("label"), MAX_REMOTE_OPTION_LENGTH)
                if label:
                    rendered.append(f"   {option_index}) {label}")
    return ("\n".join(rendered), contains_secret)


def _render_bounded_ask_user_prompt(
    *,
    locale: str,
    questions: str,
    reply_token: str,
) -> str:
    empty_prompt = format_messaging_response_text(
        locale,
        "interaction_ask_user",
        {"questions": "", "token": reply_token},
    )
    available_length = MAX_REMOTE_INTERACTION_PROMPT_LENGTH - len(empty_prompt)
    if available_length <= 1:
        raise StateError("Messaging ask_user response template exceeds the provider limit.")
    bounded_questions = questions
    if len(bounded_questions) > available_length:
        bounded_questions = f"{bounded_questions[: available_length - 1].rstrip()}…"
    return format_messaging_response_text(
        locale,
        "interaction_ask_user",
        {"questions": bounded_questions, "token": reply_token},
    )


def render_messaging_interaction_prompt(
    *,
    locale: str,
    interaction_type: str,
    task_metadata: JSONDict,
    reply_token: str,
    focus_url: str,
) -> str:
    if interaction_type == "tool_approval":
        tool_name = _bounded_text(
            task_metadata.get("tool_name"),
            MAX_REMOTE_TOOL_NAME_LENGTH,
        )
        if not tool_name:
            raise StateError("Messaging tool approval task name is invalid.")
        return format_messaging_response_text(
            locale,
            "interaction_tool_approval",
            {"tool": tool_name, "token": reply_token},
        )
    if interaction_type == "ask_user":
        questions, contains_secret = _render_questions(task_metadata)
        if contains_secret:
            return format_messaging_response_text(
                locale,
                "interaction_secret_ask_user",
                {"url": focus_url},
            )
        return _render_bounded_ask_user_prompt(
            locale=locale,
            questions=questions,
            reply_token=reply_token,
        )
    if interaction_type == "vault_secret_request":
        return format_messaging_response_text(
            locale,
            "interaction_vault_secret",
            {"url": focus_url},
        )
    raise StateError("Messaging interaction type is invalid.")
