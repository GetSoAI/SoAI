/* SoAI - Licensing settings manager capability contract [frontend/assets/ts/pages/settings/contracts/licensingManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingSettingsStatus } from '@core/api/contracts/licensingSettingsContracts.ts';
import type { LicensingLegalDocumentSet, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import type { LicensingCredentialActivationInput, LicensingLegalAcceptanceInput, LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface LicensingManagerLicensingPort {
    load(options?: { signal?: AbortSignal }): Promise<LicensingSettingsStatus>;
    acceptLicense(revision: number, fingerprint: string, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    governingDocuments(flow: LicensingLegalFlow, options: { signal: AbortSignal }): Promise<LicensingLegalDocumentSet>;
    activate(revision: number, input: LicensingCredentialActivationInput, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    convertOsEvaluation(revision: number, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[], options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    revertOsEvaluation(revision: number, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    convertCommercial(revision: number, input: LicensingCredentialActivationInput, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    reclassify(revision: number, environment: 'production' | 'non_production', options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    retrieveTerm(revision: number, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    reconcile(revision: number, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    deactivate(reason: string, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    exportOffline(revision: number, environment: 'production' | 'non_production' | null, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    importOffline(revision: number, file: File, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
    changeDeclaration(revision: number, declaration: 'personal' | 'organization_commercial', attestation: { confirmed: boolean; revision: string | null }, options: { signal: AbortSignal }): Promise<LicensingSettingsStatus>;
}

interface LicensingManagerSystemPort {
    loadVersion(options: { signal: AbortSignal }): Promise<string | null>;
}

interface LicensingManagerPagePort {
    confirmDeactivation(): Promise<boolean>;
    openPowerPage(): Promise<void>;
    subscribeStatusChanged(callback: () => void): () => void;
    notify(message: string, type: 'success' | 'error'): void;
}

interface LicensingManagerViewPort {
    requireContainer(): Element;
    updateHtml(container: Element, markup: TrustedHtml): void;
    bindEvent(container: Element, event: string, listener: (event: Event) => void): (() => void) | null;
    filter(): void;
    hasSearchQuery(): boolean;
}

interface LicensingManagerHost {
    licensing: LicensingManagerLicensingPort;
    system: LicensingManagerSystemPort;
    page: LicensingManagerPagePort;
    view: LicensingManagerViewPort;
}

export type { LicensingManagerHost };
