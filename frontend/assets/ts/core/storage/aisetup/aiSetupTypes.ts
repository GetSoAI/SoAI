/* SoAI - Shared storage AI setup state contracts [frontend/assets/ts/core/storage/aisetup/aiSetupTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelTestFailureMetadata } from '@core/openai/modelTestStreamOutcome.ts';

type AiSetupDisposition = 'in_progress' | 'handed_off' | 'finished_later' | 'skipped' | 'completed';
type AiSetupStep = 'ai_sources' | 'ai_connect' | 'ai_models' | 'ai_progress' | 'complete';
type AiSetupEngineMode = 'automatic' | 'manual';
type AiSetupModelSource = 'local' | 'cloud';
type AiSetupTestStatus = 'not_run' | 'passed' | 'stale' | 'failed';
type AiSetupTestOutcome = 'passed' | 'empty' | 'load_error' | 'timeout' | 'disconnected' | 'cancelled';

const AI_SETUP_DISPOSITIONS: readonly AiSetupDisposition[] = Object.freeze(['in_progress', 'handed_off', 'finished_later', 'skipped', 'completed']);
const AI_SETUP_STEPS: readonly AiSetupStep[] = Object.freeze(['ai_sources', 'ai_connect', 'ai_models', 'ai_progress', 'complete']);
const AI_SETUP_ENGINE_MODES: readonly AiSetupEngineMode[] = Object.freeze(['automatic', 'manual']);
const AI_SETUP_MODEL_SOURCES: readonly AiSetupModelSource[] = Object.freeze(['local', 'cloud']);
const AI_SETUP_TEST_STATUSES: readonly AiSetupTestStatus[] = Object.freeze(['not_run', 'passed', 'stale', 'failed']);
const AI_SETUP_TEST_OUTCOMES: readonly AiSetupTestOutcome[] = Object.freeze(['passed', 'empty', 'load_error', 'timeout', 'disconnected', 'cancelled']);
const AI_SETUP_MAX_MODELS = 16;
const AI_SETUP_MAX_PROVIDERS = 8;
const AI_SETUP_MAX_BACKENDS = 8;
const AI_SETUP_RESUMABLE_DISPOSITIONS: ReadonlySet<AiSetupDisposition> = new Set<AiSetupDisposition>(['in_progress', 'handed_off', 'finished_later']);
const AI_SETUP_SELECTION_STEPS: ReadonlySet<AiSetupStep> = new Set<AiSetupStep>(['ai_sources', 'ai_connect', 'ai_models']);

interface AiSetupBackend {
    pluginName: string;
    variantId: string;
    taskId: string | null;
    excluded: boolean;
}

interface AiSetupProvider {
    providerId: string;
    providerName: string;
    pluginName: string;
    excluded: boolean;
}

interface AiSetupModelTest {
    status: AiSetupTestStatus;
    outcome: AiSetupTestOutcome | null;
    configurationFingerprint: string | null;
    testedAtMs: number | null;
    failure: ModelTestFailureMetadata | null;
}

interface AiSetupModel {
    itemId: string;
    source: AiSetupModelSource;
    pluginName: string;
    catalogId: string | null;
    repositoryId: string | null;
    artifactReference: string | null;
    artifactName: string | null;
    modelId: string | null;
    downloadTaskId: string | null;
    test: AiSetupModelTest;
    excluded: boolean;
}

interface AiSetupState {
    committedLocalItemId: string | null;
    lastLocalDownloadTaskId: string | null;
    disposition: AiSetupDisposition;
    step: AiSetupStep;
    sources: { local: boolean; cloud: boolean };
    engine: { mode: AiSetupEngineMode; backends: AiSetupBackend[] };
    providers: AiSetupProvider[];
    models: AiSetupModel[];
    firstChatItemId: string | null;
    handoff: { pending: boolean; itemId: string | null };
    pendingToastShownFor: string[];
}

const isAiSetupModelReady = (model: AiSetupModel): boolean => {
    if (model.source === 'local') {
        return model.test.status === 'passed';
    }
    return model.modelId !== null && model.test.status !== 'failed';
};

const isAiSetupStateResumable = (state: AiSetupState | null): boolean => {
    if (!state || !AI_SETUP_RESUMABLE_DISPOSITIONS.has(state.disposition)) {
        return false;
    }
    if (AI_SETUP_SELECTION_STEPS.has(state.step)) {
        return true;
    }
    return state.models.some((model) => !model.excluded && !isAiSetupModelReady(model));
};

export { AI_SETUP_DISPOSITIONS, AI_SETUP_ENGINE_MODES, AI_SETUP_MAX_BACKENDS, AI_SETUP_MAX_MODELS, AI_SETUP_MAX_PROVIDERS, AI_SETUP_MODEL_SOURCES, AI_SETUP_STEPS, AI_SETUP_TEST_OUTCOMES, AI_SETUP_TEST_STATUSES, isAiSetupModelReady, isAiSetupStateResumable };
export type { AiSetupBackend, AiSetupDisposition, AiSetupEngineMode, AiSetupModel, AiSetupModelSource, AiSetupModelTest, AiSetupProvider, AiSetupState, AiSetupStep, AiSetupTestOutcome, AiSetupTestStatus };
