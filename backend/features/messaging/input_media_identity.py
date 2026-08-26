"""SoAI - Messaging provider media input identity [backend/features/messaging/input_media_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.record_fields import require_int, require_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("MessagingMediaInputIdentity", "require_messaging_media_input_identity")


@dataclass(frozen=True, slots=True)
class MessagingMediaInputIdentity:
    input_id: str
    conv_id: str
    user_id: int


def require_messaging_media_input_identity(
    input_record: JSONDict,
) -> MessagingMediaInputIdentity:
    return MessagingMediaInputIdentity(
        input_id=require_non_empty_str(
            input_record.get("input_id"),
            label="Messaging media input id",
            build_error=StateError,
        ),
        conv_id=require_non_empty_str(
            input_record.get("conv_id"),
            label="Messaging media conversation id",
            build_error=StateError,
        ),
        user_id=require_int(
            input_record.get("user_id"),
            label="Messaging media owner",
            build_error=StateError,
            minimum=1,
        ),
    )
