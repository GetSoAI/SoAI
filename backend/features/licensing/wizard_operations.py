"""SoAI - Durable licensing setup operations [backend/features/licensing/wizard_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.di.validation import require_dependencies
from core.errors.exceptions import ConcurrencyError, StateError, ValidationError
from core.licensing.canonicalization import canonicalize_licensing_json
from core.licensing.license_acceptance import require_current_license_acceptance
from core.licensing.machine_protocol import (
    prepare_activation_request,
    prepare_evaluation_request,
    prepare_operation_reconciliation_request,
)
from core.licensing.machine_request_signing import PreparedLicensingRequest
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol, LicensingWizardRepositoryProtocol
from core.licensing.trust_material import ReleaseTrustMaterial
from core.licensing.types import LicensingActivationInput
from core.meta.instance_identity import resolve_instance_identity
from core.meta.version import __version__
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.types.json import JSONDict, JSONValue
from features.licensing.machine_client import LicensingMachineClient
from features.licensing.operation_execution import (
    LicensingAttemptResult,
    LicensingOperationBinding,
    NewLicensingAttempt,
    execute_new_licensing_attempt,
    execute_operation_reconciliation,
)
from features.licensing.outcome_acceptance import (
    LicensingAcceptanceBinding,
    accept_authority_outcome,
)


@dataclass(frozen=True, slots=True)
class WizardLicensingOperationDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    wizard_repository: LicensingWizardRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    client: LicensingMachineClient
    trust_material: ReleaseTrustMaterial
    controlling_license_fingerprint: str
    document_disposition: str
    wizard_mode: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WizardLicensingOperationDependencies",
            client=self.client,
            controlling_license_fingerprint=self.controlling_license_fingerprint,
            database_plugins=self.database_plugins,
            document_disposition=self.document_disposition,
            policy=self.policy,
            repository=self.repository,
            trust_material=self.trust_material,
            wizard_mode=self.wizard_mode,
            wizard_repository=self.wizard_repository,
        )


@dataclass(frozen=True, slots=True)
class _DeploymentContext:
    private_key: Ed25519PrivateKey
    public_key: bytes
    instance_id: str


class WizardLicensingOperations:
    def __init__(self, dependencies: WizardLicensingOperationDependencies) -> None:
        self._deps = dependencies

    async def evaluate(
        self,
        *,
        draft_revision: int,
        organization: JSONDict,
        legal_acceptances: list[JSONValue],
        terms_fingerprint: str,
        now_ms: int,
    ) -> JSONDict:
        self._deps.trust_material.require_catalog()
        if not self._deps.wizard_mode or not self._deps.policy.organizational_evaluation_permitted:
            raise ValidationError("Organizational evaluation is unavailable for this flow.")
        draft = await self._deps.wizard_repository.begin_wizard_evaluation(
            expected_revision=draft_revision,
            terms_fingerprint=terms_fingerprint,
            acknowledged_at_ms=now_ms,
        )
        context = await self._deployment_context(now_ms)
        idempotency_key = secrets.token_urlsafe(24)
        prepared = prepare_evaluation_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            organization=organization,
            legal_acceptances=legal_acceptances,
        )
        return await self._execute(
            "evaluation",
            prepared,
            idempotency_key,
            context,
            int(draft["revision"]),
            now_ms,
        )

    async def activate(
        self,
        activation: LicensingActivationInput,
    ) -> JSONDict:
        self._deps.trust_material.require_catalog()
        current = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
        if current["revision"] != activation.draft_revision:
            raise ConcurrencyError("Licensing state changed before activation.")
        require_current_license_acceptance(current, self._deps.controlling_license_fingerprint)
        if current["declaration"] is None:
            raise ValidationError("Licensing product access prerequisites are missing.")
        if not self._deps.policy.product_access_required(current["declaration"]):
            raise ValidationError("Licensing product access is not required.")
        draft = current
        if self._deps.wizard_mode:
            draft = await self._deps.wizard_repository.begin_wizard_access(
                edition=self._deps.policy.edition,
                expected_revision=activation.draft_revision,
                access_flow="online_activation",
                changed_at_ms=activation.now_ms,
            )
        context = await self._deployment_context(activation.now_ms)
        idempotency_key = secrets.token_urlsafe(24)
        deployment_product = "soai_core" if self._deps.policy.edition == "soai-core" else "soai_os"
        prepared = prepare_activation_request(
            context.private_key,
            idempotency_key=idempotency_key,
            instance_id=context.instance_id,
            soai_version=str(__version__),
            deployment_product=deployment_product,
            activation_source=activation.activation_source,
            pending_evaluation_id=activation.pending_evaluation_id,
            activation_credential=activation.activation_credential,
            deployment_environment=activation.deployment_environment,
            legal_acceptances=activation.legal_acceptances,
        )
        return await self._execute(
            "activation",
            prepared,
            idempotency_key,
            context,
            int(draft["revision"]),
            activation.now_ms,
        )

    async def reconcile_operation(self, *, draft_revision: int, now_ms: int) -> JSONDict:
        self._deps.trust_material.require_catalog()
        draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.policy.edition)
        if draft["revision"] != draft_revision:
            raise ConcurrencyError("Licensing state changed before reconciliation.")
        operation = await self._deps.repository.latest_operation()
        if operation is None or operation["state"] != "outcome_unknown":
            raise ValidationError("No ambiguous licensing operation is available.")
        context = await self._deployment_context(now_ms)
        if operation["instance_id"] != context.instance_id:
            raise StateError("Licensing reconciliation instance binding changed.")
        operation_id = str(operation["operation_id"])
        if not await self._deps.repository.transition_operation(
            operation_id,
            expected_state="outcome_unknown",
            target_state="reconciling",
            updated_at_ms=now_ms,
        ):
            raise ConcurrencyError("Licensing reconciliation was claimed concurrently.")
        prepared = prepare_operation_reconciliation_request(
            context.private_key,
            idempotency_key=secrets.token_urlsafe(24),
            instance_id=context.instance_id,
            soai_version=str(__version__),
            operation_idempotency_key=str(operation["idempotency_key"]),
            request_digest=str(operation["request_digest"]),
        )
        attempt_count = operation.get("attempt_count")
        if isinstance(attempt_count, bool) or not isinstance(attempt_count, int):
            raise StateError("Stored licensing attempt count is invalid.")
        operation_type = str(operation["operation_type"])
        attempt = await execute_operation_reconciliation(
            repository=self._deps.repository,
            client=self._deps.client,
            operation_id=operation_id,
            operation_type=operation_type,
            canonical_request=prepared.canonical_document,
            attempt_count=attempt_count,
            now_ms=now_ms,
        )
        if attempt.outcome is not None and operation_type == "deactivation":
            outcome = attempt.outcome
            deployment_id = operation.get("deployment_id")
            if (
                outcome.state != "deactivated"
                or not isinstance(deployment_id, str)
                or outcome.fields.get("deployment_id") != deployment_id
            ):
                raise ValidationError("Licensing deactivation response binding is invalid.")
            await self._deps.repository.complete_deactivation_operation(
                operation_id,
                expected_state=attempt.expected_state,
                deployment_id=deployment_id,
                response_content=canonicalize_licensing_json(outcome.fields),
                completed_at_ms=now_ms,
            )
            return {"state": "deactivated", "draft_revision": draft_revision}
        return await self._accept(attempt, context, draft_revision, now_ms)

    async def _execute(
        self,
        operation_type: str,
        prepared: PreparedLicensingRequest,
        idempotency_key: str,
        context: _DeploymentContext,
        draft_revision: int,
        now_ms: int,
    ) -> JSONDict:
        attempt = await execute_new_licensing_attempt(
            repository=self._deps.repository,
            client=self._deps.client,
            attempt=NewLicensingAttempt(
                operation_type=operation_type,
                prepared=prepared,
                idempotency_key=idempotency_key,
                binding=LicensingOperationBinding(
                    edition=self._deps.policy.edition,
                    licensed_product_scope=self._deps.policy.licensed_product_scope,
                    instance_id=context.instance_id,
                ),
                now_ms=now_ms,
            ),
        )
        return await self._accept(attempt, context, draft_revision, now_ms)

    async def _accept(
        self,
        attempt: LicensingAttemptResult,
        context: _DeploymentContext,
        revision: int,
        now_ms: int,
    ) -> JSONDict:
        if attempt.outcome is None:
            return {"state": attempt.state, "draft_revision": revision}
        return await accept_authority_outcome(
            repository=self._deps.repository,
            policy=self._deps.policy,
            trust_material=self._deps.trust_material,
            document_disposition=self._deps.document_disposition,
            operation_id=attempt.operation_id,
            expected_state=attempt.expected_state,
            outcome=attempt.outcome,
            binding=LicensingAcceptanceBinding(context.public_key, context.instance_id),
            draft_revision=revision,
            now_ms=now_ms,
        )

    async def _deployment_context(self, now_ms: int) -> _DeploymentContext:
        identity = await self._deps.repository.deployment_identity(now_ms)
        instance = await resolve_instance_identity(
            self._deps.database_plugins, self._deps.repository
        )
        return _DeploymentContext(identity.private_key, identity.public_key, instance.instance_id)


__all__ = ("WizardLicensingOperationDependencies", "WizardLicensingOperations")
