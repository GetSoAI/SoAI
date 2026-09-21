"""SoAI - Infrastructure services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/infrastructure/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import httpx2

    from core.app.protocols import CommunicationsServicesProtocol
    from core.app.service_groups import HardwareRuntimeServices
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.messaging.protocols_gateway import MessagingGatewayProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.secrets.handle_store import SecretHandleStore
    from core.state.protocols import StateAggregatorProtocol
    from core.system.protocols import CommandExecutorProtocol

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
    def hardware(self) -> HardwareRuntimeServices: ...

    @property
    def prompt_token_counter(self) -> PromptTokenCounter: ...

    @property
    def command_executor(self) -> CommandExecutorProtocol | None: ...

    @property
    def secret_handle_store(self) -> SecretHandleStore: ...

    @property
    def messaging_gateway(self) -> MessagingGatewayProtocol | None: ...

    @property
    def communications(self) -> CommunicationsServicesProtocol: ...

    @property
    def conversation_attention(self) -> ConversationAttentionCoordinatorProtocol: ...
