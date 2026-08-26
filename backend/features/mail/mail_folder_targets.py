"""SoAI - Mail special-folder resolution [backend/features/mail/mail_folder_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.mail.protocols import DatabaseMailProtocol
    from features.mail.transport_models import MailAccountRuntimeState

__all__ = (
    "resolve_special_folder",
    "resolve_special_folder_remote_mailbox",
)


async def resolve_special_folder(
    *,
    database_mail: DatabaseMailProtocol,
    user_id: int,
    account_id: str,
    runtime_state: MailAccountRuntimeState,
    special_use: str,
) -> tuple[str | None, str | None]:
    folders = await database_mail.list_folders(user_id=user_id, account_id=account_id)
    for folder in folders:
        special_use_value = folder.get("special_use")
        if special_use_value != special_use:
            continue
        folder_id_value = folder.get("id")
        remote_mailbox_value = folder.get("remote_mailbox")
        folder_id = folder_id_value.strip() if isinstance(folder_id_value, str) else None
        remote_mailbox = (
            remote_mailbox_value.strip()
            if isinstance(remote_mailbox_value, str) and remote_mailbox_value.strip()
            else None
        )
        if folder_id is not None and remote_mailbox is not None:
            return folder_id, remote_mailbox
    mapped_mailbox = resolve_special_folder_remote_mailbox(
        runtime_state=runtime_state,
        special_use=special_use,
    )
    return None, mapped_mailbox


def resolve_special_folder_remote_mailbox(
    *,
    runtime_state: MailAccountRuntimeState,
    special_use: str,
) -> str | None:
    folder_mapping = runtime_state.folder_mapping
    if not isinstance(folder_mapping, dict):
        return None
    mapped_value = folder_mapping.get(special_use)
    if not isinstance(mapped_value, str):
        return None
    normalized = mapped_value.strip()
    return normalized or None
