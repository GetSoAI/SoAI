"""SoAI - Provider interaction answer grammar [backend/core/messaging/interaction_answers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = (
    "extract_messaging_interaction_tokens",
    "parse_messaging_interaction_answer",
)

TOKEN_PATTERN = r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{6})(?![0-9A-Fa-f])"


def extract_messaging_interaction_tokens(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for match in re.finditer(TOKEN_PATTERN, text):
        token = match.group(1).upper()
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens[:8])


def _without_reply_token(text: str, matched_token: str | None) -> str:
    if matched_token is None:
        return text.strip()
    removed = re.sub(
        rf"(?<![0-9A-Fa-f]){re.escape(matched_token)}(?![0-9A-Fa-f])",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return " ".join(removed.split())


def _option_labels(question: JSONDict) -> list[str]:
    options_value = question.get("options")
    if not isinstance(options_value, list):
        return []
    labels: list[str] = []
    for option in options_value:
        label_value = option.get("label") if isinstance(option, dict) else None
        if isinstance(label_value, str) and label_value.strip():
            labels.append(label_value.strip())
    return labels


def _resolve_answer_entry(answer: str, labels: list[str]) -> str:
    normalized = answer.strip()
    if not normalized:
        raise ValidationError("Interaction answer is empty.")
    if not labels:
        return normalized
    if normalized.isdecimal():
        option_index = int(normalized) - 1
        if 0 <= option_index < len(labels):
            return labels[option_index]
    matching = [label for label in labels if label.casefold() == normalized.casefold()]
    if len(matching) == 1:
        return matching[0]
    return normalized


def _answer_question(question: JSONDict, answer: str) -> list[str]:
    if question.get("isSecret") is True:
        raise ValidationError("Secret ask_user answers require authenticated Chat.")
    labels = _option_labels(question)
    if question.get("multiSelect") is True and labels:
        entries = [entry.strip() for entry in answer.split(",") if entry.strip()]
        if not entries:
            raise ValidationError("Interaction answer is empty.")
        return [_resolve_answer_entry(entry, labels) for entry in entries]
    return [_resolve_answer_entry(answer, labels)]


def _parse_numbered_answers(text: str, question_count: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    answers: dict[int, str] = {}
    for line in lines:
        match = re.fullmatch(r"(\d{1,2})\s*[:.)-]\s*(.+)", line)
        if match is None:
            raise ValidationError("Multiple questions require one numbered answer per line.")
        question_index = int(match.group(1))
        if question_index < 1 or question_index > question_count or question_index in answers:
            raise ValidationError("Numbered interaction answer is invalid.")
        answers[question_index] = match.group(2).strip()
    if set(answers) != set(range(1, question_count + 1)):
        raise ValidationError("Every interaction question requires an answer.")
    return [answers[index] for index in range(1, question_count + 1)]


def _parse_ask_user_answer(metadata: JSONDict, answer_text: str) -> JSONDict:
    questions_value = metadata.get("questions")
    if not isinstance(questions_value, list) or not questions_value:
        raise ValidationError("ask_user interaction questions are unavailable.")
    questions = [question for question in questions_value if isinstance(question, dict)]
    if len(questions) != len(questions_value):
        raise ValidationError("ask_user interaction questions are invalid.")
    raw_answers = (
        [answer_text]
        if len(questions) == 1
        else _parse_numbered_answers(answer_text, len(questions))
    )
    answers: JSONDict = {}
    for question, raw_answer in zip(questions, raw_answers, strict=True):
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValidationError("ask_user interaction question identity is invalid.")
        answers[question_id.strip()] = {
            "answers": _answer_question(question, raw_answer),
        }
    return {"answers": answers}


def parse_messaging_interaction_answer(
    *,
    interaction_type: str,
    task_metadata: JSONDict,
    text: str,
    matched_token: str | None,
) -> JSONDict:
    answer_text = _without_reply_token(text, matched_token)
    if interaction_type == "tool_approval":
        action = answer_text.casefold()
        if action in {"yes", "y"}:
            return {"action": "approve", "remember": False}
        if action == "always":
            return {"action": "approve", "remember": True}
        if action in {"no", "n"}:
            return {"action": "deny", "remember": False}
        raise ValidationError("Tool approval answer must be yes, y, no, n, or always.")
    if interaction_type == "ask_user":
        return _parse_ask_user_answer(task_metadata, answer_text)
    if interaction_type == "vault_secret_request":
        raise ValidationError("Vault secret reply requires explicit secret handling.")
    raise ValidationError("Messaging interaction type is unsupported.")
