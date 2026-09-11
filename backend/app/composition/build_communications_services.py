"""SoAI - Communications service composition [backend/app/composition/build_communications_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.background.communications_sync_actor import (
    CommunicationsSyncActor,
    CommunicationsSyncActorDependencies,
)
from app.composition.bootstrap_state_assembly_dependencies import (
    BootstrapStateAssemblyDependencies,
)
from core.concurrency.bounded_blocking import create_bounded_thread_pool
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.external_accounts.linked_account_types import LinkedAccountCapabilities
from features.calendar.account_domain import (
    CalendarAccountPolicy,
    CalendarAccountPolicyDependencies,
)
from features.calendar.dependencies import CalendarServiceDependencies
from features.calendar.service import CalendarService
from features.external_accounts.dependencies import ExternalAccountsServiceDependencies
from features.external_accounts.domain_account_creation import LinkedAccountCreation
from features.external_accounts.domain_account_listing import LinkedAccountQueries
from features.external_accounts.domain_account_oauth import LinkedAccountAuthorization
from features.external_accounts.domain_account_update import LinkedAccountMutations
from features.external_accounts.linked_account_dependencies import (
    LinkedAccountDependencies,
)
from features.external_accounts.service import ExternalAccountsService
from features.mail.account_domain import (
    MailAccountPolicy,
    MailAccountPolicyDependencies,
)
from features.mail.dependencies import MailServiceDependencies
from features.mail.service import MailService

__all__ = ("CommunicationsServices", "build_communications_services")


@dataclass(slots=True, frozen=True)
class CommunicationsServices:
    external_accounts: ExternalAccountsService
    mail: MailService
    calendar: CalendarService
    mail_accounts: LinkedAccountCapabilities
    calendar_accounts: LinkedAccountCapabilities
    sync_actor: CommunicationsSyncActor


def build_communications_services(
    deps: BootstrapStateAssemblyDependencies,
) -> CommunicationsServices:
    mail_account_locks = TTLAsyncLockRegistry[tuple[int, str]](
        TTLAsyncLockRegistryDependencies(
            ttl_seconds=3600.0,
            max_size=2000,
            cleanup_interval_seconds=300.0,
        ),
    )
    calendar_account_locks = TTLAsyncLockRegistry[tuple[int, str]](
        TTLAsyncLockRegistryDependencies(
            ttl_seconds=3600.0,
            max_size=2000,
            cleanup_interval_seconds=300.0,
        ),
    )
    external_accounts = ExternalAccountsService(
        ExternalAccountsServiceDependencies(
            config=deps.config,
            runtime_flags=deps.runtime_flags_service,
            http_client=deps.http_client,
            database_external_accounts=deps.database_services.external_accounts,
        ),
    )
    max_concurrent_per_account = max(
        1,
        int(deps.config.get_int("INTEGRATIONS.MAIL.CONCURRENCY.MAX_CONCURRENT_PER_ACCOUNT")),
    )
    mail_blocking_pool = create_bounded_thread_pool(
        label="mail_transport",
        thread_name_prefix="soai-mail",
        max_workers=max_concurrent_per_account,
        max_in_flight=max_concurrent_per_account * 4,
    )
    mail = MailService(
        MailServiceDependencies(
            config=deps.config,
            runtime_flags=deps.runtime_flags_service,
            event_bus=deps.event_bus,
            database_mail=deps.database_services.mail,
            database_files=deps.database_services.files,
            database_notifications=deps.database_services.notifications,
            external_accounts=external_accounts,
            storage_manager=deps.storage_manager,
            mail_blocking_pool=mail_blocking_pool,
            mail_account_locks=mail_account_locks,
        ),
    )
    calendar = CalendarService(
        CalendarServiceDependencies(
            config=deps.config,
            runtime_flags=deps.runtime_flags_service,
            event_bus=deps.event_bus,
            http_client=deps.http_client,
            database_calendar=deps.database_services.calendar,
            database_mail=deps.database_services.mail,
            database_notifications=deps.database_services.notifications,
            external_accounts=external_accounts,
            mail_blocking_pool=mail_blocking_pool,
            calendar_account_locks=calendar_account_locks,
            mail_account_locks=mail_account_locks,
        ),
    )
    mail_account_dependencies = LinkedAccountDependencies(
        storage=deps.database_services.mail,
        external_accounts=external_accounts,
        policy=MailAccountPolicy(
            MailAccountPolicyDependencies(
                config=deps.config,
                runtime_flags=deps.runtime_flags_service,
                database_mail=deps.database_services.mail,
                external_accounts=external_accounts,
                mail_blocking_pool=mail_blocking_pool,
                account_locks=mail_account_locks,
            ),
        ),
        account_locks=mail_account_locks,
    )
    calendar_account_dependencies = LinkedAccountDependencies(
        storage=deps.database_services.calendar,
        external_accounts=external_accounts,
        policy=CalendarAccountPolicy(
            CalendarAccountPolicyDependencies(
                config=deps.config,
                runtime_flags=deps.runtime_flags_service,
                http_client=deps.http_client,
                database_calendar=deps.database_services.calendar,
                database_mail=deps.database_services.mail,
                external_accounts=external_accounts,
                calendar_account_locks=calendar_account_locks,
                mail_account_locks=mail_account_locks,
            ),
        ),
        account_locks=calendar_account_locks,
    )
    mail_accounts = LinkedAccountCapabilities(
        creation=LinkedAccountCreation(mail_account_dependencies),
        mutations=LinkedAccountMutations(mail_account_dependencies),
        queries=LinkedAccountQueries(mail_account_dependencies),
        authorization=LinkedAccountAuthorization(mail_account_dependencies),
    )
    calendar_accounts = LinkedAccountCapabilities(
        creation=LinkedAccountCreation(calendar_account_dependencies),
        mutations=LinkedAccountMutations(calendar_account_dependencies),
        queries=LinkedAccountQueries(calendar_account_dependencies),
        authorization=LinkedAccountAuthorization(calendar_account_dependencies),
    )
    sync_actor = CommunicationsSyncActor(
        CommunicationsSyncActorDependencies(
            startup_ready_event=deps.runtime_foundation.runtime_state.startup_ready_event,
            config=deps.config,
            database_users=deps.database_services.users,
            database_calendar=deps.database_services.calendar,
            database_notifications=deps.database_services.notifications,
            mail=mail,
            calendar=calendar,
            mail_account_queries=mail_accounts.queries,
            calendar_account_queries=calendar_accounts.queries,
            cancellation_binder=deps.cancellation_system.binder,
            finalizer_tracker=deps.cancellation_system.finalizer_tracker,
        ),
    )
    return CommunicationsServices(
        external_accounts=external_accounts,
        mail=mail,
        calendar=calendar,
        mail_accounts=mail_accounts,
        calendar_accounts=calendar_accounts,
        sync_actor=sync_actor,
    )
