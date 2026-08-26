"""SoAI - Authenticated licensing deactivation [backend/features/licensing/maintenance_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets

from core.errors.exceptions import ValidationError
from core.licensing.canonicalization import canonicalize_licensing_json
from core.licensing.deployment_request_protocol import prepare_deactivation_request
from core.meta.version import __version__
from core.types.json import JSONDict
from features.licensing.maintenance_dependencies import LicensingMaintenanceDependencies
from features.licensing.online_entitlement import load_active_online_entitlement
from features.licensing.operation_execution import (
    NewLicensingAttempt,
    execute_new_licensing_attempt,
)


class LicensingMaintenanceOperations:
    def __init__(self, dependencies: LicensingMaintenanceDependencies) -> None:
        self._deps = dependencies

    async def deactivate(self, reason: str, now_ms: int) -> JSONDict:
        context = await load_active_online_entitlement(
            policy=self._deps.policy,
            repository=self._deps.repository,
            database_plugins=self._deps.database_plugins,
            trust_material=self._deps.trust_material,
            now_ms=now_ms,
        )
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_deactivation_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
            reason=reason,
        )
        attempt = await execute_new_licensing_attempt(
            repository=self._deps.repository,
            client=self._deps.client,
            attempt=NewLicensingAttempt(
                operation_type="deactivation",
                prepared=prepared,
                idempotency_key=idempotency_key,
                binding=context.operation_binding(self._deps.policy.edition),
                deactivation_reason=reason,
                now_ms=now_ms,
            ),
        )
        if attempt.outcome is None:
            return {"state": attempt.state}
        outcome = attempt.outcome
        if (
            outcome.state != "deactivated"
            or outcome.fields.get("deployment_id") != context.validated.deployment_id
        ):
            await self._deps.repository.transition_operation(
                attempt.operation_id,
                expected_state=attempt.expected_state,
                target_state="failed",
                terminal_code="invalid_contract",
                updated_at_ms=now_ms,
            )
            raise ValidationError("Licensing deactivation response binding is invalid.")
        await self._deps.repository.complete_deactivation_operation(
            attempt.operation_id,
            expected_state=attempt.expected_state,
            deployment_id=context.validated.deployment_id,
            response_content=canonicalize_licensing_json(outcome.fields),
            completed_at_ms=now_ms,
        )
        return {"state": "deactivated"}


__all__ = ("LicensingMaintenanceOperations",)
