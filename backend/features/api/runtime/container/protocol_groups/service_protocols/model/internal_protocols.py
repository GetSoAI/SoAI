"""SoAI - Model services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/model/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPServicesCoordinatorProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelProviderCoordinatorProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )

__all__ = (
    "ModelContextProtocolServicesProtocol",
    "ModelServicesProtocol",
)


class ModelServicesProtocol(Protocol):
    @property
    def model_resolution_service(self) -> ModelResolutionServiceProtocol: ...

    @property
    def model_information_service(self) -> ModelInformationServiceProtocol: ...

    @property
    def model_parameter_service(self) -> ModelParameterServiceProtocol: ...

    @property
    def model_virtual_model_service(self) -> VirtualModelServiceProtocol: ...

    @property
    def model_provider_coordinator(self) -> ModelProviderCoordinatorProtocol: ...


class ModelContextProtocolServicesProtocol(Protocol):
    @property
    def coordinator(self) -> MCPServicesCoordinatorProtocol: ...
