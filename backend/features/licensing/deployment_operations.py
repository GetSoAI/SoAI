"""SoAI - Licensed deployment transition operations [backend/features/licensing/deployment_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ConcurrencyError, ValidationError
from core.licensing.deployment_request_protocol import (
    prepare_commercial_conversion_request,
    prepare_deployment_reclassification_request,
    prepare_os_evaluation_conversion_request,
    prepare_os_evaluation_reversion_request,
    prepare_term_renewal_request,
)
from core.licensing.machine_request_signing import PreparedLicensingRequest
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol, LicensingWizardRepositoryProtocol
from core.licensing.trust_material import ReleaseTrustMaterial
from core.meta.version import __version__
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.types.json import JSONDict, JSONValue
from features.licensing.machine_client import LicensingMachineClient
from features.licensing.online_entitlement import (
    ActiveOnlineEntitlement,
    load_active_online_entitlement,
)
from features.licensing.operation_execution import (
    NewLicensingAttempt,
    execute_new_licensing_attempt,
)
from features.licensing.outcome_acceptance import (
    LicensingAcceptanceBinding,
    accept_authority_outcome,
)


@dataclass(frozen=True, slots=True)
class LicensingDeploymentOperationDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    wizard_repository: LicensingWizardRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    client: LicensingMachineClient
    trust_material: ReleaseTrustMaterial

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingDeploymentOperationDependencies",
            client=self.client,
            database_plugins=self.database_plugins,
            policy=self.policy,
            repository=self.repository,
            trust_material=self.trust_material,
            wizard_repository=self.wizard_repository,
        )


class LicensingDeploymentOperations:
    def __init__(self, dependencies: LicensingDeploymentOperationDependencies) -> None:
        self._deps = dependencies

    async def convert_os_evaluation(
        self,
        draft_revision: int,
        organization: JSONDict,
        legal_acceptances: list[JSONValue],
        now_ms: int,
    ) -> JSONDict:
        await self._require_revision(draft_revision)
        context = await self._context(now_ms)
        if (
            self._deps.policy.edition != "soai-os"
            or context.parsed.entitlement_type != "personal_os_perpetual"
        ):
            raise ValidationError("OS evaluation conversion requires Personal SoAI OS.")
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_os_evaluation_conversion_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
            organization=organization,
            legal_acceptances=legal_acceptances,
        )
        return await self._execute(
            "os-evaluation-conversion", prepared, idempotency_key, context, now_ms
        )

    async def revert_os_evaluation(self, draft_revision: int, now_ms: int) -> JSONDict:
        await self._require_revision(draft_revision)
        context = await self._context(now_ms)
        if (
            self._deps.policy.edition != "soai-os"
            or context.parsed.entitlement_type != "organization_evaluation"
        ):
            raise ValidationError("OS evaluation reversion requires an OS evaluation.")
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_os_evaluation_reversion_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
        )
        return await self._execute(
            "os-evaluation-reversion", prepared, idempotency_key, context, now_ms
        )

    async def convert_commercial(
        self,
        draft_revision: int,
        activation_credential: str,
        deployment_environment: str,
        legal_acceptances: list[JSONValue],
        now_ms: int,
    ) -> JSONDict:
        await self._require_revision(draft_revision)
        context = await self._context(now_ms)
        idempotency_key = secrets.token_urlsafe(24)
        deployment_product = "soai_core" if self._deps.policy.edition == "soai-core" else "soai_os"
        prepared = prepare_commercial_conversion_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
            activation_credential=activation_credential,
            deployment_product=deployment_product,
            deployment_environment=deployment_environment,
            legal_acceptances=legal_acceptances,
        )
        return await self._execute(
            "commercial-conversion", prepared, idempotency_key, context, now_ms
        )

    async def reclassify(
        self, draft_revision: int, deployment_environment: str, now_ms: int
    ) -> JSONDict:
        await self._require_revision(draft_revision)
        context = await self._context(now_ms)
        if context.parsed.entitlement_type not in {
            "commercial_term",
            "commercial_continuity",
            "commercial_full_perpetual",
        }:
            raise ValidationError("Only a commercial deployment can be reclassified.")
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_deployment_reclassification_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
            deployment_environment=deployment_environment,
        )
        return await self._execute(
            "deployment-reclassification", prepared, idempotency_key, context, now_ms
        )

    async def retrieve_term(self, draft_revision: int, now_ms: int) -> JSONDict:
        await self._require_revision(draft_revision)
        context = await self._context(now_ms)
        values = context.parsed.values
        current_term_id = values.get("term_id")
        if current_term_id is None and context.parsed.entitlement_type == "commercial_continuity":
            current_term_id = values.get("previous_term_id")
        if not isinstance(current_term_id, str):
            raise ValidationError("Term retrieval requires a commercial annual entitlement.")
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_term_renewal_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_id=context.validated.deployment_id,
            entitlement_generation=context.validated.generation,
            current_term_id=current_term_id,
        )
        return await self._execute("term-renewal", prepared, idempotency_key, context, now_ms)

    async def _execute(
        self,
        operation_type: str,
        prepared: PreparedLicensingRequest,
        idempotency_key: str,
        context: ActiveOnlineEntitlement,
        now_ms: int,
    ) -> JSONDict:
        new_attempt = NewLicensingAttempt(
            operation_type=operation_type,
            prepared=prepared,
            idempotency_key=idempotency_key,
            binding=context.operation_binding(self._deps.policy.edition),
            now_ms=now_ms,
        )
        attempt = await execute_new_licensing_attempt(
            repository=self._deps.repository,
            client=self._deps.client,
            attempt=new_attempt,
        )
        draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
        if attempt.outcome is None:
            return {"state": attempt.state, "draft_revision": int(draft["revision"])}
        return await accept_authority_outcome(
            repository=self._deps.repository,
            policy=self._deps.policy,
            trust_material=self._deps.trust_material,
            document_disposition="active",
            operation_id=attempt.operation_id,
            expected_state=attempt.expected_state,
            outcome=attempt.outcome,
            binding=LicensingAcceptanceBinding(context.public_key, context.instance_id),
            draft_revision=int(draft["revision"]),
            now_ms=now_ms,
        )

    async def _context(self, now_ms: int) -> ActiveOnlineEntitlement:
        return await load_active_online_entitlement(
            policy=self._deps.policy,
            repository=self._deps.repository,
            database_plugins=self._deps.database_plugins,
            trust_material=self._deps.trust_material,
            now_ms=now_ms,
        )

    async def _require_revision(self, expected_revision: int) -> None:
        draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
        if draft["revision"] != expected_revision:
            raise ConcurrencyError("Licensing state changed before the deployment operation.")


__all__ = ("LicensingDeploymentOperationDependencies", "LicensingDeploymentOperations")
