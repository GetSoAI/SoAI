"""SoAI - Mail service dependencies [backend/features/mail/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.files.protocols import DatabaseFilesProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.mail.protocols import DatabaseMailProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("MailServiceDependencies",)


@dataclass(frozen=True, slots=True)
class MailServiceDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    event_bus: EventBusProtocol
    database_mail: DatabaseMailProtocol
    database_files: DatabaseFilesProtocol
    database_notifications: DatabaseNotificationsProtocol
    external_accounts: ExternalAccountsServiceProtocol
    storage_manager: StorageManagerProtocol
    mail_blocking_pool: BoundedBlockingPool
    mail_account_locks: AsyncLockRegistryProtocol[tuple[int, str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MailServiceDependencies",
            config=self.config,
            runtime_flags=self.runtime_flags,
            event_bus=self.event_bus,
            database_mail=self.database_mail,
            database_files=self.database_files,
            database_notifications=self.database_notifications,
            external_accounts=self.external_accounts,
            storage_manager=self.storage_manager,
            mail_blocking_pool=self.mail_blocking_pool,
            mail_account_locks=self.mail_account_locks,
        )
