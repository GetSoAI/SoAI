"""SoAI - Required model service resolution for manager assembly [backend/app/composition/model_service_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.service_preconditions import require_initialized

if TYPE_CHECKING:
    from app.types_services_runtime import ModelServices
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelManagerProtocol,
        ModelParameterServiceProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )

__all__ = ("require_model_orchestration_services",)


def require_model_orchestration_services(
    model_services: ModelServices,
) -> tuple[
    ModelManagerProtocol,
    ModelResolutionServiceProtocol,
    ModelInformationServiceProtocol,
    ModelParameterServiceProtocol,
    VirtualModelServiceProtocol,
]:
    model_manager_instance = require_initialized(
        model_services.model_coordinator,
        message="Model coordinator must be initialized before managers are built.",
    )
    model_resolution_service = require_initialized(
        model_services.model_resolution_service,
        message="Model resolution service must be initialized before managers are built.",
    )
    model_information_service = require_initialized(
        model_services.model_information_service,
        message="Model information service must be initialized before managers are built.",
    )
    model_parameter_service = require_initialized(
        model_services.model_parameter_service,
        message="Model parameter service must be initialized before managers are built.",
    )
    model_virtual_model_service = require_initialized(
        model_services.model_virtual_model_service,
        message="Virtual model service must be initialized before managers are built.",
    )
    return (
        model_manager_instance,
        model_resolution_service,
        model_information_service,
        model_parameter_service,
        model_virtual_model_service,
    )
