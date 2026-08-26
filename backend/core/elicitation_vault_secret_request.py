"""SoAI - Shared vault_secret_request elicitation helpers [backend/core/elicitation_vault_secret_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.web.site_scope import SiteScope, site_scope_from_url
from core.web.site_scope_codec import coerce_site_scope_json_dict, parse_site_scope_obj

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_vault_secret_request_task_metadata",
    "extract_vault_secret_request_prompt_payload",
    "require_vault_secret_request_scope",
)

CREDENTIAL_REQUEST_INTERACTION_TYPE = "vault_secret_request"


def build_vault_secret_request_task_metadata(
    *,
    current_page_url: str,
    title: str,
    message: str,
    allow_save_to_vault: bool,
    save_label_default: str | None = None,
) -> JSONDict:
    scope = site_scope_from_url(current_page_url)
    scope_payload = coerce_site_scope_json_dict(scope)
    metadata: JSONDict = {
        "interaction_type": CREDENTIAL_REQUEST_INTERACTION_TYPE,
        "current_page_url": current_page_url,
        "scope": scope_payload,
        "title": title,
        "message": message,
        "allow_save_to_vault": bool(allow_save_to_vault),
        "fields": [
            {
                "id": "username",
                "type": "text",
                "optional": True,
            },
            {
                "id": "password",
                "type": "password",
                "optional": False,
            },
        ],
    }
    if isinstance(save_label_default, str) and save_label_default.strip():
        metadata["save_label_default"] = save_label_default.strip()
    return metadata


def extract_vault_secret_request_prompt_payload(task: Task) -> JSONDict | None:
    metadata = task.metadata
    interaction_type = metadata.get("interaction_type")
    if (
        not isinstance(interaction_type, str)
        or interaction_type.strip() != CREDENTIAL_REQUEST_INTERACTION_TYPE
    ):
        return None
    title_value = metadata.get("title")
    message_value = metadata.get("message")
    fields_value = metadata.get("fields")
    scope = parse_site_scope_obj(metadata.get("scope"))
    allow_save_to_vault = metadata.get("allow_save_to_vault")
    save_label_default_value = metadata.get("save_label_default")
    if not isinstance(title_value, str) or not title_value.strip():
        return None
    if not isinstance(message_value, str) or not message_value.strip():
        return None
    if not isinstance(fields_value, list) or not fields_value:
        return None
    if scope is None:
        return None
    save_label_default = (
        save_label_default_value.strip()
        if isinstance(save_label_default_value, str) and save_label_default_value.strip()
        else None
    )
    return {
        "task_id": task.task_id,
        "title": title_value.strip(),
        "message": message_value.strip(),
        "fields": list(fields_value),
        "scope": coerce_site_scope_json_dict(scope),
        "allow_save_to_vault": (
            bool(allow_save_to_vault) if isinstance(allow_save_to_vault, bool) else True
        ),
        "save_label_default": save_label_default,
        "created_at_ms": int(task.created_at_ms),
    }


def require_vault_secret_request_scope(metadata: Mapping[str, JSONValue]) -> SiteScope | None:
    return parse_site_scope_obj(metadata.get("scope"))
