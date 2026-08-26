"""SoAI - Atomic conversation interaction task mutations [backend/core/tasks/interaction_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.web.site_scope import SiteScope

__all__ = (
    "ConversationInteractionMutation",
    "VaultSecretHandoffMutation",
)


@dataclass(frozen=True, slots=True)
class VaultSecretHandoffMutation:
    user_id: int
    conv_id: str
    checkpoint_generation: int | None
    scope: SiteScope
    username: str | None
    password: str = field(repr=False)
    expires_at_ms: int
    saved_credential_id: str | None = None
    saved_credential_label: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationInteractionMutation:
    checkpoint_generation: int | None = None
    remembered_tool_permission: str | None = None
    vault_secret_handoff: VaultSecretHandoffMutation | None = None
