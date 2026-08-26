"""SoAI - Conversation interaction payload extraction and validation [backend/features/chat/interaction_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_ask_user import (
    ASK_USER_INTERACTION_TYPE,
    extract_ask_user_prompt_payload,
)
from core.elicitation_interactions import (
    extract_notification_id,
    normalize_interaction_type,
)
from core.elicitation_vault_secret_request import (
    CREDENTIAL_REQUEST_INTERACTION_TYPE,
    extract_vault_secret_request_prompt_payload,
)
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE
from core.tool_approval.task_metadata import extract_tool_approval_prompt_payload
from core.types.json import is_json_list

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("extract_interaction_payload",)


def extract_interaction_payload(task: Task, interaction_type: str) -> JSONDict | None:
    metadata = dict(task.metadata)
    interaction_key = normalize_interaction_type(metadata.get("interaction_type"))
    if interaction_key is None or interaction_key != interaction_type:
        return None
    created_at_ms = int(task.created_at_ms)
    notification_id = extract_notification_id(metadata)
    if interaction_type == ASK_USER_INTERACTION_TYPE:
        payload = extract_ask_user_prompt_payload(task)
        if payload is None:
            return None
        questions_value = payload.get("questions")
        if not is_json_list(questions_value) or not questions_value:
            return None
        return {
            "task_id": task.task_id,
            "interaction_type": interaction_type,
            "notification_id": notification_id,
            "created_at_ms": created_at_ms,
            "payload": {"questions": list(questions_value)},
        }
    if interaction_type == CREDENTIAL_REQUEST_INTERACTION_TYPE:
        payload = extract_vault_secret_request_prompt_payload(task)
        if payload is None:
            return None
        return {
            "task_id": task.task_id,
            "interaction_type": interaction_type,
            "notification_id": notification_id,
            "created_at_ms": created_at_ms,
            "payload": {
                "title": payload.get("title"),
                "message": payload.get("message"),
                "fields": payload.get("fields"),
                "scope": payload.get("scope"),
                "allow_save_to_vault": payload.get("allow_save_to_vault"),
                "save_label_default": payload.get("save_label_default"),
            },
        }
    if interaction_type == TOOL_APPROVAL_INTERACTION_TYPE:
        payload = extract_tool_approval_prompt_payload(task)
        if payload is None:
            return None
        return {
            "task_id": task.task_id,
            "interaction_type": interaction_type,
            "notification_id": notification_id,
            "created_at_ms": created_at_ms,
            "payload": {
                "tool_name": payload.get("tool_name"),
                "tool_call_id": payload.get("tool_call_id"),
                "tool_arguments": payload.get("tool_arguments"),
            },
        }
    return None
