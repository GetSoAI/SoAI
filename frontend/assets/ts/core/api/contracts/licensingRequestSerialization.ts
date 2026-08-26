/* SoAI - Final licensing V1 request serialization [frontend/assets/ts/core/api/contracts/licensingRequestSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingLegalDocumentSet } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import type { DeploymentEnvironment } from '@core/api/contracts/licensingEntitlementContracts.ts';
import type { WizardDeclaration } from '@core/api/contracts/wizardLicensingContracts.ts';
import { wallClockMs } from '@core/time/clock.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface LicensingOrganizationInput {
    legalName: string;
    countryCode: string;
    registrationOrTaxId: string;
    authorizedAcceptorName: string;
    authorizedAcceptorEmail: string;
    authorityAttested: true;
}

interface LicensingLegalAcceptanceInput {
    documentId: string;
    fingerprint: string;
    version: string;
    acceptedAt: string;
}

interface LicensingCredentialActivationInput {
    activationCredential: string;
    deploymentEnvironment: DeploymentEnvironment | null;
    legalAcceptances: readonly LicensingLegalAcceptanceInput[];
}

const requireDraftRevision = (draftRevision: number): void => {
    if (!Number.isSafeInteger(draftRevision) || draftRevision < 0) throw new TypeError('Licensing draft revision is invalid.');
};

const requireCredential = (credential: string): void => {
    if (typeof credential !== 'string' || credential.length < 16 || credential.length > 192) throw new TypeError('Licensing activation credential length is invalid.');
};

const serializeOrganization = (organization: LicensingOrganizationInput): JsonObject => {
    const values = [organization.legalName, organization.registrationOrTaxId, organization.authorizedAcceptorName];
    if (values.some((value) => !value || value.trim() !== value || value.length > 256 || /[\u0000-\u001f]/.test(value))) throw new TypeError('Licensing organization identity is invalid.');
    if (!/^[A-Z]{2}$/.test(organization.countryCode) || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(organization.authorizedAcceptorEmail) || organization.authorizedAcceptorEmail.length > 320 || organization.authorityAttested !== true) throw new TypeError('Licensing organization authority is invalid.');
    return { 'legal_name': organization.legalName, 'country_code': organization.countryCode, 'registration_or_tax_id': organization.registrationOrTaxId, 'authorized_acceptor_name': organization.authorizedAcceptorName, 'authorized_acceptor_email': organization.authorizedAcceptorEmail, 'authority_attested': true };
};

const serializeAcceptances = (acceptances: readonly LicensingLegalAcceptanceInput[]): JsonObject[] => {
    if (!acceptances.length) throw new TypeError('Licensing legal acceptance is required.');
    const sorted = [...acceptances].sort((left, right) => left.documentId.localeCompare(right.documentId, 'en'));
    if (new Set(sorted.map((acceptance) => acceptance.documentId)).size !== sorted.length) throw new TypeError('Licensing legal acceptances must be unique.');
    return sorted.map((acceptance) => {
        if (!/^[a-z][a-z0-9_]{1,63}$/.test(acceptance.documentId) || !/^sha256:[a-f0-9]{64}$/.test(acceptance.fingerprint) || !/^[1-9][0-9]*\.[0-9]+$/.test(acceptance.version) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(acceptance.acceptedAt)) throw new TypeError('Licensing legal acceptance is invalid.');
        return { 'document_id': acceptance.documentId, fingerprint: acceptance.fingerprint, version: acceptance.version, 'accepted_at': acceptance.acceptedAt };
    });
};

const licensingLegalAcceptances = (documents: LicensingLegalDocumentSet, acceptedAtMs: number = wallClockMs()): LicensingLegalAcceptanceInput[] => {
    if (!Number.isSafeInteger(acceptedAtMs) || acceptedAtMs < 0) throw new TypeError('Licensing acceptance time is invalid.');
    const acceptedAt = new Date(Math.floor(acceptedAtMs / 1000) * 1000).toISOString().replace('.000Z', 'Z');
    return documents.documents.map((document) => ({ documentId: document.documentId, fingerprint: document.fingerprint, version: document.version, acceptedAt }));
};

const serializeLicensingRevisionRequest = (draftRevision: number): JsonObject => {
    requireDraftRevision(draftRevision);
    return { 'schema_version': 1, 'draft_revision': draftRevision };
};

const serializeLicensingDeclarationRequest = (draftRevision: number, declaration: WizardDeclaration, attestation: { confirmed: boolean; revision: string | null }): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), declaration, 'attestation_confirmed': attestation.confirmed, 'attestation_revision': attestation.revision });
const serializeLicenseAcceptanceRequest = (draftRevision: number, fingerprint: string): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), fingerprint });

const serializeEvaluationRequest = (draftRevision: number, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[]): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), organization: serializeOrganization(organization), 'legal_acceptances': serializeAcceptances(legalAcceptances) });

const serializeEvaluationActivationRequest = (draftRevision: number, pendingEvaluationId: string, legalAcceptances: readonly LicensingLegalAcceptanceInput[]): JsonObject => {
    if (pendingEvaluationId.length < 16 || pendingEvaluationId.length > 128) throw new TypeError('Licensing pending evaluation identity is invalid.');
    return { ...serializeLicensingRevisionRequest(draftRevision), 'activation_source': 'evaluation', 'pending_evaluation_id': pendingEvaluationId, 'activation_credential': null, 'deployment_environment': null, 'legal_acceptances': serializeAcceptances(legalAcceptances) };
};

const serializeLicensingActivationRequest = (draftRevision: number, input: LicensingCredentialActivationInput): string => {
    requireCredential(input.activationCredential);
    return JSON.stringify({ ...serializeLicensingRevisionRequest(draftRevision), 'activation_source': 'credential', 'pending_evaluation_id': null, 'activation_credential': input.activationCredential, 'deployment_environment': input.deploymentEnvironment, 'legal_acceptances': serializeAcceptances(input.legalAcceptances) });
};

const serializeOsEvaluationConversionRequest = (draftRevision: number, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[]): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), organization: serializeOrganization(organization), 'legal_acceptances': serializeAcceptances(legalAcceptances) });
const serializeOsEvaluationReversionRequest = (draftRevision: number): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), 'company_use_ended': true, 'company_data_handled': true });
const serializeCommercialConversionRequest = (draftRevision: number, input: LicensingCredentialActivationInput): string => {
    requireCredential(input.activationCredential);
    if (input.deploymentEnvironment === null) throw new TypeError('Commercial conversion requires a deployment environment.');
    return JSON.stringify({ ...serializeLicensingRevisionRequest(draftRevision), 'activation_credential': input.activationCredential, 'deployment_environment': input.deploymentEnvironment, 'legal_acceptances': serializeAcceptances(input.legalAcceptances) });
};
const serializeDeploymentReclassificationRequest = (draftRevision: number, environment: DeploymentEnvironment): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), 'deployment_environment': environment });
const serializeLicensingDeactivationRequest = (reason: string): JsonObject => ({ 'schema_version': 1, reason });
const serializeLicensingOfflineRequest = (draftRevision: number, environment: DeploymentEnvironment | null, licenseReference: string | null): JsonObject => ({ ...serializeLicensingRevisionRequest(draftRevision), 'deployment_environment': environment, 'license_reference': licenseReference });

export { licensingLegalAcceptances, serializeCommercialConversionRequest, serializeDeploymentReclassificationRequest, serializeEvaluationActivationRequest, serializeEvaluationRequest, serializeLicenseAcceptanceRequest, serializeLicensingActivationRequest, serializeLicensingDeactivationRequest, serializeLicensingDeclarationRequest, serializeLicensingOfflineRequest, serializeLicensingRevisionRequest, serializeOsEvaluationConversionRequest, serializeOsEvaluationReversionRequest };
export type { LicensingCredentialActivationInput, LicensingLegalAcceptanceInput, LicensingOrganizationInput };
