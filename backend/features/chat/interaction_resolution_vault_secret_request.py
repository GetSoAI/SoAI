"""SoAI - Vault secret request interaction resolution [backend/features/chat/interaction_resolution_vault_secret_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.elicitation_vault_secret_request import (
    extract_vault_secret_request_prompt_payload,
    require_vault_secret_request_scope,
)
from core.errors.exceptions import ValidationError
from core.tasks.enums import TaskStatus
from core.tasks.interaction_mutations import (
    ConversationInteractionMutation,
    VaultSecretHandoffMutation,
)
from core.tasks.interaction_secrets import interaction_secret_handoff_ttl_ms
from core.timing.epoch import epoch_ms
from core.validation.strings import coerce_optional_trimmed_str
from features.chat.interaction_resolution_support import (
    build_interaction_resolution_response,
    finalize_interaction_resolution,
)

if TYPE_CHECKING:
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("resolve_vault_secret_request_interaction",)

OPERATION_CREDENTIAL_REQUEST_FINALIZE = (
    "features.chat.interaction_service.vault_secret_request_finalize"
)


async def resolve_vault_secret_request_interaction(
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    conv_id: str,
    user_id: int,
    payload: JSONDict,
    checkpoint_generation: int | None,
) -> JSONDict:
    prompt = extract_vault_secret_request_prompt_payload(task)
    if prompt is None:
        raise ValidationError("Task does not contain a valid vault_secret_request payload.")
    scope = require_vault_secret_request_scope(prompt)
    if scope is None:
        raise ValidationError("Task does not contain a valid scope.")
    password = payload.get("password")
    if not isinstance(password, str) or not password:
        raise ValidationError("password is required")
    username_value = payload.get("username")
    username = coerce_optional_trimmed_str(username_value)
    save_to_vault = payload.get("save_to_vault") is True
    saved_credential_id: str | None = None
    saved_credential_label: str | None = None
    if save_to_vault:
        if prompt.get("allow_save_to_vault") is not True:
            raise ValidationError(
                "This vault secret prompt does not allow saving to the vault.",
            )
        label_value = payload.get("label")
        saved_credential_label = coerce_optional_trimmed_str(label_value)
        if not saved_credential_label:
            raise ValidationError("label is required when save_to_vault is true")
        saved_credential_id = str(uuid.uuid4())
    resolved = await finalize_interaction_resolution(
        task_registry=task_registry,
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result={
            "secret_handoff": True,
            "saved_credential_id": saved_credential_id,
        },
        status_message="User submitted",
        operation=OPERATION_CREDENTIAL_REQUEST_FINALIZE,
        conv_id=conv_id,
        interaction_mutation=ConversationInteractionMutation(
            checkpoint_generation=checkpoint_generation,
            vault_secret_handoff=VaultSecretHandoffMutation(
                user_id=user_id,
                conv_id=conv_id,
                checkpoint_generation=checkpoint_generation,
                scope=scope,
                username=username,
                password=password,
                saved_credential_id=saved_credential_id,
                saved_credential_label=saved_credential_label,
                expires_at_ms=epoch_ms() + interaction_secret_handoff_ttl_ms(),
            ),
        ),
    )
    return build_interaction_resolution_response(
        task_id=resolved.task_id,
        status=resolved.status.value,
    )
