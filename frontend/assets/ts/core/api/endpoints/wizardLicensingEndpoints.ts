/* SoAI - Wizard licensing V1 API endpoints [frontend/assets/ts/core/api/endpoints/wizardLicensingEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import { decodeLicensingOfflineRequest } from '@core/api/contracts/licensingOfflineRequestContract.ts';
import { decodeLicensingLegalDocumentSet, type LicensingLegalDocumentSet, type LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { serializeEvaluationActivationRequest, serializeEvaluationRequest, serializeLicenseAcceptanceRequest, serializeLicensingActivationRequest, serializeLicensingDeclarationRequest, serializeLicensingOfflineRequest, serializeLicensingRevisionRequest, type LicensingCredentialActivationInput, type LicensingLegalAcceptanceInput, type LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';
import { decodeWizardLicensingDocument, type WizardLicensingDocumentResponse } from '@core/api/contracts/wizardLicensingMutations.ts';
import { decodeWizardStatusResponse, type WizardDeclaration, type WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { requireOfflineEntitlementFile } from '@core/licensing/offlineEntitlementFile.ts';

interface WizardLicensingEndpoints {
    acceptLicense(draftRevision: number, fingerprint: string, options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    declareUse(draftRevision: number, declaration: WizardDeclaration, attestation: { confirmed: boolean; revision: string | null }, options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    evaluationTerms(options?: LicensingRequestOptions): Promise<WizardLicensingDocumentResponse>;
    personalPurchaseTerms(options?: LicensingRequestOptions): Promise<WizardLicensingDocumentResponse>;
    governingDocuments(flow: LicensingLegalFlow, options?: LicensingRequestOptions): Promise<LicensingLegalDocumentSet>;
    startEvaluation(draftRevision: number, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[], options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    activateCredential(draftRevision: number, input: LicensingCredentialActivationInput, options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    activateEvaluation(draftRevision: number, pendingEvaluationId: string, legalAcceptances: readonly LicensingLegalAcceptanceInput[], options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    reconcileOperation(draftRevision: number, options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
    exportOfflineRequest(draftRevision: number, deploymentEnvironment: 'production' | 'non_production' | null, options?: LicensingRequestOptions): Promise<BufferedApiResponse>;
    importOfflineCertificate(draftRevision: number, file: File, options?: LicensingRequestOptions): Promise<WizardStatusResponse>;
}

interface LicensingRequestOptions {
    signal?: AbortSignal;
}

const createWizardLicensingEndpoints = (api: ApiClientContext): WizardLicensingEndpoints => ({
    acceptLicense: async (draftRevision, fingerprint, options = {}) => decodeWizardStatusResponse(await api.post('/api/v1/webui/wizard/license/accept', serializeLicenseAcceptanceRequest(draftRevision, fingerprint), options)),
    declareUse: async (draftRevision, declaration, attestation, options = {}) => decodeWizardStatusResponse(await api.put('/api/v1/webui/wizard/use', serializeLicensingDeclarationRequest(draftRevision, declaration, attestation), options)),
    evaluationTerms: async (options = {}) => decodeWizardLicensingDocument(await api.get('/api/v1/webui/wizard/licensing/evaluation-terms', { cache: 'no-store', signal: options.signal })),
    personalPurchaseTerms: async (options = {}) => decodeWizardLicensingDocument(await api.get('/api/v1/webui/wizard/licensing/personal-purchase-terms', { cache: 'no-store', signal: options.signal })),
    governingDocuments: async (flow, options = {}) => decodeLicensingLegalDocumentSet(await api.get(`/api/v1/webui/wizard/licensing/governing-documents/${flow}`, { cache: 'no-store', signal: options.signal })),
    startEvaluation: async (draftRevision, organization, legalAcceptances, options = {}) => decodeWizardStatusResponse(await api.post('/api/v1/webui/wizard/licensing/evaluation', serializeEvaluationRequest(draftRevision, organization, legalAcceptances), options)),
    activateCredential: async (draftRevision, input, options = {}) => decodeWizardStatusResponse(await api.post('/api/v1/webui/wizard/licensing/activation', serializeLicensingActivationRequest(draftRevision, input), options)),
    activateEvaluation: async (draftRevision, pendingEvaluationId, legalAcceptances, options = {}) => decodeWizardStatusResponse(await api.post('/api/v1/webui/wizard/licensing/activation', serializeEvaluationActivationRequest(draftRevision, pendingEvaluationId, legalAcceptances), options)),
    reconcileOperation: async (draftRevision, options = {}) => decodeWizardStatusResponse(await api.post('/api/v1/webui/wizard/licensing/operation-reconciliation', serializeLicensingRevisionRequest(draftRevision), options)),
    exportOfflineRequest: async (draftRevision, deploymentEnvironment, options = {}) => decodeLicensingOfflineRequest(await api.post('/api/v1/webui/wizard/licensing/offline-request', serializeLicensingOfflineRequest(draftRevision, deploymentEnvironment, null), { rawResponse: true, bufferRawResponse: true, cache: 'no-store', signal: options.signal })),
    importOfflineCertificate: async (draftRevision, file, options = {}) => {
        requireOfflineEntitlementFile(file);
        return decodeWizardStatusResponse(await api.uploadFile('/api/v1/webui/wizard/licensing/offline-import', file, { 'draft_revision': String(draftRevision) }, { cache: 'no-store', signal: options.signal }));
    }
});

export { createWizardLicensingEndpoints };
export type { WizardLicensingEndpoints };
