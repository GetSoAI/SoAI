"""SoAI - Elicitation ask_user answer normalization [backend/core/elicitation_ask_user_answers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_ask_user import (
    collect_ask_user_question_ids,
    extract_ask_user_prompt_payload,
)
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("normalize_ask_user_answers",)


def normalize_ask_user_answers(task: Task, answers: JSONDict) -> JSONDict:
    question_payload = extract_ask_user_prompt_payload(task)
    if question_payload is None:
        raise ValidationError("Task does not contain a valid ask_user prompt.")
    question_ids = collect_ask_user_question_ids(question_payload)
    answer_keys = set(answers.keys())
    if answer_keys != question_ids:
        missing = sorted(question_ids - answer_keys)
        extra = sorted(answer_keys - question_ids)
        problems: list[str] = []
        if missing:
            problems.append(f"missing answers for: {', '.join(missing)}")
        if extra:
            problems.append(f"unexpected answers for: {', '.join(extra)}")
        raise ValidationError("; ".join(problems))
    normalized_answers: JSONDict = {}
    for question_id in sorted(question_ids):
        answer_value = answers.get(question_id)
        if not isinstance(answer_value, dict):
            raise ValidationError(f"invalid answer payload for: {question_id}")
        choices_value = answer_value.get("answers")
        if not isinstance(choices_value, list):
            raise ValidationError(f"invalid answers list for: {question_id}")
        if len(choices_value) < 1:
            raise ValidationError(f"answers must contain at least one entry for: {question_id}")
        normalized_choices: list[str] = []
        for entry in choices_value:
            if not isinstance(entry, str):
                raise ValidationError(f"invalid answer entry for: {question_id}")
            normalized_entry = entry.strip()
            if not normalized_entry:
                raise ValidationError(f"invalid answer entry for: {question_id}")
            normalized_choices.append(normalized_entry)
        normalized_answers[question_id] = {"answers": normalized_choices}
    return {"answers": normalized_answers}
