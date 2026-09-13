"""SoAI - Infrastructure services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/infrastructure/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import httpx2

    from core.calendar.protocols import CalendarServiceProtocol
    from core.events.protocols import EventBusProtocol
    from core.external_accounts.linked_account_types import LinkedAccountCapabilities
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.hardware.protocols import (
        HardwareControlServiceProtocol,
        HardwareGpuTuningProtocol,
        HardwareManagerProtocol,
    )
    from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.messaging.gateway.protocols import MessagingGatewayProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.secrets.handle_store import SecretHandleStore
    from core.state.protocols import StateAggregatorProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.terminal.protocols import TerminalServiceProtocol

__all__ = ("InfrastructureServicesProtocol",)


class InfrastructureServicesProtocol(Protocol):
    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def log_manager(self) -> LoggingManagerProtocol: ...

    @property
    def metrics_manager(self) -> MetricsManagerProtocol: ...

    @property
    def state_aggregator(self) -> StateAggregatorProtocol: ...

    @property
    def http_client(self) -> httpx2.AsyncClient: ...

    @property
    def hw_manager(self) -> HardwareManagerProtocol: ...

    @property
    def hw_gpu_tuning(self) -> HardwareGpuTuningProtocol: ...

    @property
    def hardware_control(self) -> HardwareControlServiceProtocol: ...

    @property
    def hardware_soaibench(self) -> SoAIBenchServiceProtocol: ...

    @property
    def terminal(self) -> TerminalServiceProtocol: ...

    @property
    def storage_manager(self) -> StorageManagerProtocol: ...

    @property
    def prompt_token_counter(self) -> PromptTokenCounter: ...

    @property
    def command_executor(self) -> CommandExecutorProtocol | None: ...

    @property
    def secret_handle_store(self) -> SecretHandleStore: ...

    @property
    def messaging_gateway(self) -> MessagingGatewayProtocol | None: ...

    @property
    def external_accounts(self) -> ExternalAccountsServiceProtocol: ...

    @property
    def mail_accounts(self) -> LinkedAccountCapabilities: ...

    @property
    def calendar_accounts(self) -> LinkedAccountCapabilities: ...

    @property
    def mail(self) -> MailServiceProtocol: ...

    @property
    def calendar(self) -> CalendarServiceProtocol: ...

    @property
    def conversation_attention(self) -> ConversationAttentionCoordinatorProtocol: ...
