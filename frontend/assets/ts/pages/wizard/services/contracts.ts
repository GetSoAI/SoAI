/* SoAI - Wizard service contracts [frontend/assets/ts/pages/wizard/services/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardCompletionResult } from '@core/auth/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { WizardState, WizardStepId } from '@features/wizard/public.ts';
import type { ProductAccessFlow, WizardAccountUi, WizardUi, WizardViewContext } from '@pages/wizard/types.ts';
import type { WizardDeclaration, WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { WizardLicensingDocumentResponse } from '@core/api/contracts/wizardLicensingMutations.ts';
import type { LicensingLegalDocumentSet, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import type { LicensingCredentialActivationInput, LicensingLegalAcceptanceInput, LicensingOrganizationInput } from '@core/api/contracts/licensingRequestSerialization.ts';

interface WizardViewPort {
    state: WizardState;
    requireUi(): WizardUi;
    requireAccountUi(): WizardAccountUi;
    isDomUsable(): boolean;
    createViewContext(): WizardViewContext;
    updateProgress(ui: WizardUi): void;
    syncNavigation(ui: WizardUi, stepId: WizardStepId): void;
    syncUseSelection(ui: WizardUi): void;
    selectedProductAccessFlow(ui: WizardUi): ProductAccessFlow | null;
    syncProductAccessSelection(ui: WizardUi, selected: ProductAccessFlow | null, focusPanel: boolean): void;
    updateText(element: HTMLElement, value: string): void;
    toggleHidden(element: HTMLElement, hidden: boolean): void;
    updateHTML(element: HTMLElement, value: TrustedHtml): void;
}

interface WizardDataPort {
    submitWizardAccount(username: string, password: string): Promise<WizardCompletionResult>;
    markWizardHasUsers(): void;
    persistWizardState(): Promise<void>;
    markWizardFirstRunModalsPending(): Promise<void>;
    fetchLicenseText(): Promise<string>;
    acceptLicense(status: WizardStatusResponse): Promise<WizardStatusResponse>;
    declareUse(status: WizardStatusResponse, declaration: WizardDeclaration, confirmed: boolean): Promise<WizardStatusResponse>;
    evaluationTerms(): Promise<WizardLicensingDocumentResponse>;
    personalPurchaseTerms(): Promise<WizardLicensingDocumentResponse>;
    governingDocuments(flow: LicensingLegalFlow): Promise<LicensingLegalDocumentSet>;
    startEvaluation(status: WizardStatusResponse, organization: LicensingOrganizationInput, legalAcceptances: readonly LicensingLegalAcceptanceInput[]): Promise<WizardStatusResponse>;
    activateCredential(status: WizardStatusResponse, input: LicensingCredentialActivationInput): Promise<WizardStatusResponse>;
    activateEvaluation(status: WizardStatusResponse, pendingEvaluationId: string, legalAcceptances: readonly LicensingLegalAcceptanceInput[]): Promise<WizardStatusResponse>;
    reconcile(status: WizardStatusResponse): Promise<WizardStatusResponse>;
    exportOffline(status: WizardStatusResponse, environment: 'production' | 'non_production' | null): Promise<WizardStatusResponse>;
    importOffline(status: WizardStatusResponse, file: File): Promise<WizardStatusResponse>;
    refreshStatus(): Promise<WizardStatusResponse | null>;
    applyStatus(status: WizardStatusResponse): void;
    invalidateLicensingRequests(): void;
}

interface WizardCompletionPort {
    dispatchWizardCompleted(): void;
    navigateAfterCompletion(isSessionActivationRequired: boolean): Promise<void>;
    refreshLogos(): void;
    logWarn(operation: string, error: Error): void;
    logError(operation: string, error: Error): void;
    notify(message: string, notificationType: 'success' | 'error' | 'warning' | 'info'): void;
}

interface WizardPageServiceHost {
    view: WizardViewPort;
    data: WizardDataPort;
    completion: WizardCompletionPort;
}

export type { WizardPageServiceHost };
