"""SoAI - Database task interaction checkpoint operations [backend/database/repositories/tasks/service_conversation_interactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.security.secret_crypto import decrypt_required_secret
from core.serialization.json_parsing import parse_json_dict
from core.tasks.interaction_secrets import (
    ClaimedInteractionSecret,
    InteractionSecretClaimIdentity,
    InteractionSecretEffectUnknownError,
)
from core.timing.epoch import epoch_ms
from core.web.site_scope_codec import parse_site_scope_obj
from database.repositories.tasks.conversation_interaction_queries import (
    has_conversation_interaction_checkpoint,
)
from database.repositories.tasks.conversation_interaction_secrets import (
    InteractionSecretEffectUnknownClaim,
    sync_claim_interaction_secret,
    sync_consume_interaction_secret_after_tool_checkpoint,
    sync_consume_interaction_secrets_after_turn_checkpoint,
    sync_mark_interaction_secret_downstream_started,
)
from database.repositories.tasks.internal_protocols import (
    DatabaseTasksCoreAndSecretsOwnerProtocol,
)

__all__ = (
    "claim_interaction_secret",
    "consume_interaction_secret_after_tool_checkpoint",
    "consume_interaction_secrets_after_turn_checkpoint",
    "has_interaction_checkpoint",
    "mark_interaction_secret_downstream_started",
)


async def has_interaction_checkpoint(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    *,
    input_id: str,
    task_id: str,
) -> bool:
    return await self.core.reader.execute_read(
        has_conversation_interaction_checkpoint,
        input_id,
        task_id,
    )


async def claim_interaction_secret(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    *,
    task_id: str,
    user_id: int,
    conv_id: str,
    claim_owner: str,
) -> ClaimedInteractionSecret | None:
    claimed = await self.core.writer.queue_write_operation(
        sync_claim_interaction_secret,
        task_id,
        user_id,
        conv_id,
        claim_owner,
        epoch_ms(),
    )
    if claimed is None:
        return None
    if isinstance(claimed, InteractionSecretEffectUnknownClaim):
        raise InteractionSecretEffectUnknownError(
            "Secret-consuming tool effect is unknown after interruption.",
        )
    plaintext = decrypt_required_secret(
        self.fernets,
        claimed.ciphertext,
        label="task interaction secret handoff",
    )
    payload = parse_json_dict(plaintext, field="Task interaction secret handoff")
    scope = parse_site_scope_obj(payload.get("scope"))
    username_value = payload.get("username")
    password_value = payload.get("password")
    if scope is None or not isinstance(password_value, str) or not password_value:
        raise StateError("Task interaction secret handoff payload is invalid.")
    username = username_value if isinstance(username_value, str) else None
    return ClaimedInteractionSecret(
        identity=InteractionSecretClaimIdentity(
            task_id=claimed.task_id,
            claim_generation=claimed.claim_generation,
            claim_owner=claimed.claim_owner,
        ),
        user_id=claimed.user_id,
        conv_id=claimed.conv_id,
        scope=scope,
        username=username,
        password=password_value,
    )


async def mark_interaction_secret_downstream_started(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    *,
    identity: InteractionSecretClaimIdentity,
    tool_call_id: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_mark_interaction_secret_downstream_started,
        identity.task_id,
        identity.claim_generation,
        identity.claim_owner,
        tool_call_id,
        epoch_ms(),
    )


async def consume_interaction_secret_after_tool_checkpoint(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    *,
    task_id: str,
) -> bool:
    return await self.core.writer.queue_write_operation(
        sync_consume_interaction_secret_after_tool_checkpoint,
        task_id,
        epoch_ms(),
    )


async def consume_interaction_secrets_after_turn_checkpoint(
    self: DatabaseTasksCoreAndSecretsOwnerProtocol,
    *,
    turn_id: str,
    iteration_index: int,
) -> int:
    return await self.core.writer.queue_write_operation(
        sync_consume_interaction_secrets_after_turn_checkpoint,
        turn_id,
        iteration_index,
        epoch_ms(),
    )
