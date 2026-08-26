/* SoAI - Authenticated licensing administration endpoints [frontend/assets/ts/core/api/endpoints/webuiLicensingEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeLicensingSettingsStatus, type LicensingSettingsStatus } from '@core/api/contracts/licensingSettingsContracts.ts';
import { decodeLicensingOfflineRequest } from '@core/api/contracts/licensingOfflineRequestContract.ts';
import { decodeLicensingLegalDocumentSet, type LicensingLegalDocumentSet, type LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { serializeCommercialConversionRequest, serializeDeploymentReclassificationRequest, serializeLicenseAcceptanceRequest, serializeLicensingActivationRequest, serializeLicensingDeactivationRequest, serializeLicensingDeclarationRequest, serializeLicensingOfflineRequest, serializeLicensingRevisionRequest, serializeOsEvaluationConversionRequest, serializeOsEvaluationReversionRequest, type LicensingCredentialActivationInput, type LicensingLegalAcceptanceInput, type LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { WizardDeclaration } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { requireOfflineEntitlementFile } from '@core/licensing/offlineEntitlementFile.ts';

interface WebuiLicensingEndpoints {
    status(options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    acceptLicense(draftRevision: number, fingerprint: string, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    governingDocuments(flow: LicensingLegalFlow, options?: { signal?: AbortSignal }): Promise<LicensingLegalDocumentSet>;
    activate(draftRevision: number, input: LicensingCredentialActivationInput, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    reconcile(draftRevision: number, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    convertOsEvaluation(draftRevision: number, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[], options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    revertOsEvaluation(draftRevision: number, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    convertCommercial(draftRevision: number, input: LicensingCredentialActivationInput, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    reclassify(draftRevision: number, environment: 'production' | 'non_production', options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    retrieveTerm(draftRevision: number, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    deactivate(reason: string, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    exportOfflineRequest(draftRevision: number, environment: 'production' | 'non_production' | null, options?: { signal?: AbortSignal }): Promise<BufferedApiResponse>;
    importOfflineCertificate(draftRevision: number, file: File, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    changeDeclaration(draftRevision: number, declaration: WizardDeclaration, attestation: { confirmed: boolean; revision: string | null }, options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
}

const createWebuiLicensingEndpoints = (api: ApiClientContext): WebuiLicensingEndpoints => ({
    status: async (options = {}) => decodeLicensingSettingsStatus(await api.get('/api/v1/webui/licensing/status', { cache: 'no-store', signal: options.signal })),
    governingDocuments: async (flow, options = {}) => decodeLicensingLegalDocumentSet(await api.get(`/api/v1/webui/licensing/governing-documents/${flow}`, { cache: 'no-store', signal: options.signal })),
    acceptLicense: async (draftRevision, fingerprint, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/license/accept', serializeLicenseAcceptanceRequest(draftRevision, fingerprint), options)),
    activate: async (draftRevision, input, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/activation', serializeLicensingActivationRequest(draftRevision, input), options)),
    reconcile: async (draftRevision, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/operation-reconciliation', serializeLicensingRevisionRequest(draftRevision), options)),
    convertOsEvaluation: async (draftRevision, organization, legalAcceptances, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/os-evaluation-conversion', serializeOsEvaluationConversionRequest(draftRevision, organization, legalAcceptances), options)),
    revertOsEvaluation: async (draftRevision, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/os-evaluation-reversion', serializeOsEvaluationReversionRequest(draftRevision), options)),
    convertCommercial: async (draftRevision, input, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/commercial-conversion', serializeCommercialConversionRequest(draftRevision, input), options)),
    reclassify: async (draftRevision, environment, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/deployment-reclassification', serializeDeploymentReclassificationRequest(draftRevision, environment), options)),
    retrieveTerm: async (draftRevision, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/term-renewal', serializeLicensingRevisionRequest(draftRevision), options)),
    deactivate: async (reason, options = {}) => decodeLicensingSettingsStatus(await api.post('/api/v1/webui/licensing/deactivation', serializeLicensingDeactivationRequest(reason), options)),
    exportOfflineRequest: async (draftRevision, environment, options = {}) => decodeLicensingOfflineRequest(await api.post('/api/v1/webui/licensing/offline-request', serializeLicensingOfflineRequest(draftRevision, environment, null), { ...options, rawResponse: true, bufferRawResponse: true, cache: 'no-store' })),
    importOfflineCertificate: async (draftRevision, file, options = {}) => {
        requireOfflineEntitlementFile(file);
        return decodeLicensingSettingsStatus(await api.uploadFile('/api/v1/webui/licensing/offline-import', file, { 'draft_revision': String(draftRevision) }, { cache: 'no-store', signal: options.signal }));
    },
    changeDeclaration: async (draftRevision, declaration, attestation, options = {}) => decodeLicensingSettingsStatus(await api.put('/api/v1/webui/licensing/declaration', serializeLicensingDeclarationRequest(draftRevision, declaration, attestation), options))
});

export { createWebuiLicensingEndpoints };
export type { WebuiLicensingEndpoints };
