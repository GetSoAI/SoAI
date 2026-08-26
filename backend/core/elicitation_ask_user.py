"""SoAI - Shared ask_user elicitation helpers [backend/core/elicitation_ask_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ASK_USER_INTERACTION_TYPE",
    "build_ask_user_task_metadata",
    "collect_ask_user_question_ids",
    "extract_ask_user_prompt_payload",
)

ASK_USER_INTERACTION_TYPE = "ask_user"


def build_ask_user_task_metadata(questions: list[JSONDict]) -> JSONDict:
    return {
        "interaction_type": ASK_USER_INTERACTION_TYPE,
        "questions": questions,
    }


def extract_ask_user_prompt_payload(task: Task) -> JSONDict | None:
    metadata = task.metadata
    interaction_type = metadata.get("interaction_type")
    if (
        not isinstance(interaction_type, str)
        or interaction_type.strip() != ASK_USER_INTERACTION_TYPE
    ):
        return None
    questions_raw = metadata.get("questions")
    if not isinstance(questions_raw, list):
        return None
    questions: list[JSONValue] = []
    for entry in questions_raw:
        if isinstance(entry, dict):
            questions.append(dict(entry))
    if not questions:
        return None
    return {
        "task_id": task.task_id,
        "questions": questions,
        "created_at_ms": int(task.created_at_ms),
    }


def collect_ask_user_question_ids(payload: Mapping[str, JSONValue]) -> set[str]:
    question_ids: set[str] = set()
    questions_value = payload.get("questions")
    if not isinstance(questions_value, list):
        return question_ids
    for question_value in questions_value:
        if not isinstance(question_value, dict):
            continue
        question_id_value = question_value.get("id")
        if not isinstance(question_id_value, str):
            continue
        question_id = question_id_value.strip()
        if question_id:
            question_ids.add(question_id)
    return question_ids
