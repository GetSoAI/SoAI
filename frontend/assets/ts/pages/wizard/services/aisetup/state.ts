/* SoAI - Wizard AI setup stored state transitions [frontend/assets/ts/pages/wizard/services/aisetup/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AI_SETUP_MAX_MODELS, AI_SETUP_MAX_PROVIDERS, AI_SETUP_STEPS, isAiSetupModelReady, type AiSetupDisposition, type AiSetupEngineMode, type AiSetupModel, type AiSetupProvider, type AiSetupState, type AiSetupStep, type AiSetupTestOutcome } from '@core/storage/aisetup/aiSetupTypes.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';

interface LocalModelPick {
    catalogId: string | null;
    pluginName: string;
    repositoryId: string;
    artifactReference: string;
    artifactName: string;
}

interface CloudModelPick {
    pluginName: string;
    modelId: string;
}

const UNTESTED: AiSetupModel['test'] = { status: 'not_run', outcome: null, configurationFingerprint: null, testedAtMs: null };

const createAiSetupState = (): AiSetupState => ({
    disposition: 'in_progress',
    step: 'ai_sources',
    sources: { local: false, cloud: false },
    engine: { mode: 'automatic', backends: [] },
    providers: [],
    models: [],
    firstChatItemId: null,
    handoff: { pending: false, itemId: null },
    pendingToastShownFor: []
});

const updateModel = (state: AiSetupState, itemId: string, update: (model: AiSetupModel) => AiSetupModel): AiSetupState => ({ ...state, models: state.models.map((model) => (model.itemId === itemId ? update(model) : model)) });

const isModelStarted = (model: AiSetupModel): boolean => model.downloadTaskId !== null || (model.source === 'local' && model.modelId !== null);

const pruneReferences = (state: AiSetupState): AiSetupState => {
    const itemIds = new Set(state.models.map((model) => model.itemId));
    const selectable = new Set(state.models.filter((model) => !model.excluded).map((model) => model.itemId));
    const handoffItemId = state.handoff.itemId !== null && itemIds.has(state.handoff.itemId) ? state.handoff.itemId : null;
    return {
        ...state,
        firstChatItemId: state.firstChatItemId !== null && selectable.has(state.firstChatItemId) ? state.firstChatItemId : null,
        handoff: { pending: state.handoff.pending && handoffItemId !== null, itemId: handoffItemId },
        pendingToastShownFor: state.pendingToastShownFor.filter((itemId) => itemIds.has(itemId))
    };
};

const withStepReached = (state: AiSetupState, step: AiSetupStep): AiSetupState => (AI_SETUP_STEPS.indexOf(step) > AI_SETUP_STEPS.indexOf(state.step) ? { ...state, step } : state);

const withDisposition = (state: AiSetupState, disposition: AiSetupDisposition): AiSetupState => ({ ...state, disposition });

const withSources = (state: AiSetupState, sources: AiSetupState['sources']): AiSetupState => {
    let next: AiSetupState = { ...state, sources: { ...sources } };
    if (!sources.local)
        next = withEngineChoice(
            reconcileSelection(next, 'local', () => false, []),
            next.engine.mode,
            []
        );
    if (!sources.cloud) next = reconcileSelection(next, 'cloud', () => false, []);
    return next;
};

const withEngineChoice = (state: AiSetupState, mode: AiSetupEngineMode, choices: readonly { pluginName: string; variantId: string }[]): AiSetupState => {
    const chosen = new Set(choices.map((choice) => choice.pluginName));
    const kept = state.engine.backends.map((backend) => (chosen.has(backend.pluginName) ? { ...backend, excluded: false } : { ...backend, excluded: true })).filter((backend) => !backend.excluded || backend.taskId !== null);
    const added = choices.filter((choice) => !kept.some((backend) => backend.pluginName === choice.pluginName)).map((choice) => ({ pluginName: choice.pluginName, variantId: choice.variantId, taskId: null, excluded: false }));
    return { ...state, engine: { mode, backends: [...kept, ...added] } };
};

const withBackendTask = (state: AiSetupState, pluginName: string, variantId: string, taskId: string | null): AiSetupState => {
    const backend = { pluginName, variantId, taskId, excluded: false };
    const exists = state.engine.backends.some((entry) => entry.pluginName === pluginName);
    const backends = exists ? state.engine.backends.map((entry) => (entry.pluginName === pluginName ? backend : entry)) : [...state.engine.backends, backend];
    return { ...state, engine: { ...state.engine, backends } };
};

const withBackendExcluded = (state: AiSetupState, pluginName: string): AiSetupState => ({
    ...state,
    engine: { ...state.engine, backends: state.engine.backends.map((backend) => (backend.pluginName === pluginName ? { ...backend, excluded: true } : backend)) }
});

const withProvider = (state: AiSetupState, provider: Omit<AiSetupProvider, 'excluded'>): AiSetupState => {
    const previous = state.providers.filter((entry) => entry.providerId !== provider.providerId).map((entry) => ({ ...entry, excluded: true }));
    const providers = [...previous, { ...provider, excluded: false }].slice(-AI_SETUP_MAX_PROVIDERS);
    const selections = activeProvider(state)?.providerId === provider.providerId ? state : reconcileSelection(state, 'cloud', () => false, []);
    return pruneReferences({ ...selections, providers });
};

const activeProvider = (state: AiSetupState): AiSetupProvider | null => state.providers.filter((provider) => !provider.excluded).at(-1) ?? null;

const createModel = (fields: Pick<AiSetupModel, 'source' | 'pluginName' | 'catalogId' | 'repositoryId' | 'artifactReference' | 'artifactName' | 'modelId'>): AiSetupModel => ({
    itemId: generateSecureId({ prefix: 'ai-item', separator: '-' }),
    ...fields,
    downloadTaskId: null,
    test: UNTESTED,
    excluded: false
});

const reconcileSelection = (state: AiSetupState, source: AiSetupModel['source'], matches: (model: AiSetupModel) => boolean, additions: readonly AiSetupModel[]): AiSetupState => {
    const others = state.models.filter((model) => model.source !== source);
    const current = state.models
        .filter((model) => model.source === source)
        .flatMap((model) => {
            if (matches(model)) return [{ ...model, excluded: false }];
            return isModelStarted(model) ? [{ ...model, excluded: true }] : [];
        });
    const models = [...others, ...current, ...additions];
    if (models.length > AI_SETUP_MAX_MODELS) throw new RangeError('AI setup model selection exceeds the model limit');
    return pruneReferences({ ...state, models });
};

const isSameArtifact = (model: AiSetupModel, pick: LocalModelPick): boolean => model.pluginName === pick.pluginName && model.repositoryId === pick.repositoryId && model.artifactReference === pick.artifactReference;

const withLocalSelection = (state: AiSetupState, picks: readonly LocalModelPick[]): AiSetupState => {
    const existing = state.models.filter((model) => model.source === 'local');
    const additions = picks.filter((pick) => !existing.some((model) => isSameArtifact(model, pick))).map((pick) => createModel({ source: 'local', pluginName: pick.pluginName, catalogId: pick.catalogId, repositoryId: pick.repositoryId, artifactReference: pick.artifactReference, artifactName: pick.artifactName, modelId: null }));
    return reconcileSelection(state, 'local', (model) => picks.some((pick) => isSameArtifact(model, pick)), additions);
};

const withCloudSelection = (state: AiSetupState, picks: readonly CloudModelPick[]): AiSetupState => {
    const existing = state.models.filter((model) => model.source === 'cloud');
    const matches = (model: AiSetupModel, pick: CloudModelPick): boolean => model.pluginName === pick.pluginName && model.modelId === pick.modelId;
    const additions = picks.filter((pick) => !existing.some((model) => matches(model, pick))).map((pick) => createModel({ source: 'cloud', pluginName: pick.pluginName, catalogId: null, repositoryId: null, artifactReference: null, artifactName: null, modelId: pick.modelId }));
    return reconcileSelection(state, 'cloud', (model) => picks.some((pick) => matches(model, pick)), additions);
};

const withModelTask = (state: AiSetupState, itemId: string, downloadTaskId: string | null): AiSetupState => updateModel(state, itemId, (model) => ({ ...model, downloadTaskId }));

const withModelDiscovered = (state: AiSetupState, itemId: string, modelId: string): AiSetupState => updateModel(state, itemId, (model) => ({ ...model, modelId }));

const withConfiguration = (state: AiSetupState, itemId: string, configurationFingerprint: string): AiSetupState => updateModel(state, itemId, (model) => ({ ...model, test: { ...UNTESTED, configurationFingerprint } }));

const withTestResult = (state: AiSetupState, itemId: string, outcome: AiSetupTestOutcome, configurationFingerprint: string | null, testedAtMs: number): AiSetupState => updateModel(state, itemId, (model) => ({ ...model, test: { status: outcome === 'passed' ? 'passed' : 'failed', outcome, configurationFingerprint, testedAtMs } }));

const withTestStale = (state: AiSetupState, itemId: string): AiSetupState => updateModel(state, itemId, (model) => (model.test.status === 'passed' ? { ...model, test: { ...model.test, status: 'stale' } } : model));

const withItemExcluded = (state: AiSetupState, itemId: string): AiSetupState => pruneReferences(updateModel(state, itemId, (model) => ({ ...model, excluded: true })));

const withFirstChat = (state: AiSetupState, itemId: string | null): AiSetupState => pruneReferences({ ...state, firstChatItemId: itemId });

const withHandoff = (state: AiSetupState, pending: boolean, itemId: string | null): AiSetupState => pruneReferences({ ...state, handoff: { pending, itemId } });

const withToastShown = (state: AiSetupState, itemIds: readonly string[]): AiSetupState => pruneReferences({ ...state, pendingToastShownFor: [...new Set([...state.pendingToastShownFor, ...itemIds])] });

const selectedModels = (state: AiSetupState): AiSetupModel[] => state.models.filter((model) => !model.excluded);

const resolveDefaultFirstChatItemId = (state: AiSetupState): string | null => {
    const models = selectedModels(state);
    const chosen = models.find((model) => model.itemId === state.firstChatItemId);
    if (chosen) return chosen.itemId;
    return (models.find((model) => model.source === 'cloud') ?? models.find((model) => model.source === 'local'))?.itemId ?? null;
};

const resolveHandoffItemId = (state: AiSetupState, isReady: (model: AiSetupModel) => boolean = isAiSetupModelReady): string | null => {
    const models = selectedModels(state);
    const preferred = models.find((model) => model.itemId === resolveDefaultFirstChatItemId(state));
    if (preferred && isReady(preferred)) return preferred.itemId;
    return models.find((model) => isReady(model))?.itemId ?? null;
};

export { activeProvider, createAiSetupState, resolveDefaultFirstChatItemId, resolveHandoffItemId, selectedModels, withBackendExcluded, withBackendTask, withCloudSelection, withConfiguration, withDisposition, withEngineChoice, withFirstChat, withHandoff, withItemExcluded, withLocalSelection, withModelDiscovered, withModelTask, withProvider, withSources, withStepReached, withTestResult, withTestStale, withToastShown };
export type { CloudModelPick, LocalModelPick };
