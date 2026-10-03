/* SoAI - Wizard page contracts constants [frontend/assets/ts/pages/wizard/contracts/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AiSetupWizardStepId, WizardState, WizardStepId } from '@features/wizard/public.ts';

export const AI_SETUP_WIZARD_STEP_IDS: ReadonlyArray<AiSetupWizardStepId> = ['ai_sources', 'ai_connect', 'ai_models', 'ai_progress'];

export const isAiSetupWizardStepId = (stepId: WizardStepId): stepId is AiSetupWizardStepId => AI_SETUP_WIZARD_STEP_IDS.some((aiStepId) => aiStepId === stepId);

export const deriveAiSetupStepIds = (includeConnect: boolean): ReadonlyArray<AiSetupWizardStepId> => AI_SETUP_WIZARD_STEP_IDS.filter((stepId) => includeConnect || stepId !== 'ai_connect');

export const deriveWizardStepIds = (state: Pick<WizardState, 'requiresProductAccess' | 'aiSetupSteps' | 'isAiSetupResume' | 'isSessionActivationRequired'>): ReadonlyArray<WizardStepId> => {
    if (state.isAiSetupResume) return [...state.aiSetupSteps, 'complete'];
    const productAccessSteps: ReadonlyArray<WizardStepId> = state.requiresProductAccess ? ['product_access'] : [];
    const aiSetupSteps = state.isSessionActivationRequired ? [] : state.aiSetupSteps;
    return ['welcome', 'license', 'use', ...productAccessSteps, 'account', ...aiSetupSteps, 'complete'];
};

export const syncWizardSteps = (state: WizardState): void => {
    const currentStepId = state.steps[state.stepIndex];
    state.steps = deriveWizardStepIds(state);
    state.totalSteps = state.steps.length;
    const currentIndex = currentStepId === undefined ? -1 : state.steps.indexOf(currentStepId);
    if (currentIndex >= 0) state.stepIndex = currentIndex;
};

export const requireWizardStepId = (steps: readonly WizardStepId[], index: number): WizardStepId => {
    const stepId = steps[index];
    if (!stepId) throw new Error(`WizardPage: invalid step index ${String(index)}`);
    return stepId;
};
