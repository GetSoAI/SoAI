/* SoAI - Wizard feature state [frontend/assets/ts/features/wizard/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiUser } from '@core/auth/types.ts';
import type { WizardCompletedSummary, WizardDeclaration, WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import type { WizardLicensingDocumentResponse } from '@core/api/contracts/wizardLicensingMutations.ts';
import type { LicensingLegalDocumentSet, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import type { AiSetupStep } from '@core/storage/aisetup/aiSetupTypes.ts';

type AiSetupWizardStepId = Exclude<AiSetupStep, 'complete'>;

type WizardStepId = 'welcome' | 'license' | 'use' | 'product_access' | 'account' | AiSetupWizardStepId | 'complete';

interface WizardState {
    stepIndex: number;
    totalSteps: number;
    licenseText: string;
    adminUser: WebuiUser | null;
    completedSummary: WizardCompletedSummary | null;
    isSessionActivationRequired: boolean;
    isBusy: boolean;
    accountSubmissionPending: boolean;
    status: WizardStatusResponse | null;
    steps: readonly WizardStepId[];
    requiresProductAccess: boolean;
    aiSetupSteps: readonly AiSetupWizardStepId[];
    isAiSetupResume: boolean;
    declarationSelection: WizardDeclaration | null;
    attestationConfirmed: boolean;
    inlineError: string | null;
    evaluationTerms: WizardLicensingDocumentResponse | null;
    personalPurchaseTerms: WizardLicensingDocumentResponse | null;
    evaluationAcknowledged: boolean;
    legalDocumentSets: Map<LicensingLegalFlow, LicensingLegalDocumentSet>;
}

const createInitialWizardState = (): WizardState => {
    return {
        stepIndex: 0,
        totalSteps: 0,
        licenseText: '',
        adminUser: null,
        completedSummary: null,
        isSessionActivationRequired: false,
        isBusy: false,
        accountSubmissionPending: false,
        status: null,
        steps: ['welcome', 'license', 'use', 'account', 'ai_sources', 'ai_connect', 'ai_models', 'ai_progress', 'complete'],
        requiresProductAccess: false,
        aiSetupSteps: ['ai_sources', 'ai_connect', 'ai_models', 'ai_progress'],
        isAiSetupResume: false,
        declarationSelection: null,
        attestationConfirmed: false,
        inlineError: null,
        evaluationTerms: null,
        personalPurchaseTerms: null,
        evaluationAcknowledged: false,
        legalDocumentSets: new Map()
    };
};

export { createInitialWizardState };
export type { AiSetupWizardStepId, WizardState, WizardStepId };
