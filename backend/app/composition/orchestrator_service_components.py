"""SoAI - Named orchestrator service component bundle [backend/app/composition/orchestrator_service_components.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from orchestrator.execution.active_inference_service import ActiveInferenceService
from orchestrator.execution.inference_executor import OrchestratorInferenceExecutor
from orchestrator.execution.outcomes import OutcomeManager
from orchestrator.handlers import OrchestratorHandlers
from orchestrator.lifecycle.service import OrchestratorLifecycle


@dataclass(frozen=True, slots=True)
class OrchestratorServiceComponents:
    queue: OrchestratorQueueProtocol
    scheduler: OrchestratorSchedulerProtocol
    inference_executor: OrchestratorInferenceExecutor
    outcomes: OutcomeManager
    active_inferences: ActiveInferenceService
    handlers: OrchestratorHandlers
    lifecycle: OrchestratorLifecycle
    control: OrchestratorControlProtocol


__all__ = ("OrchestratorServiceComponents",)
