/* SoAI - Shared storage AI setup state codec [frontend/assets/ts/core/storage/aisetup/aiSetupCodec.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AI_SETUP_DISPOSITIONS, AI_SETUP_ENGINE_MODES, AI_SETUP_MAX_BACKENDS, AI_SETUP_MAX_MODELS, AI_SETUP_MAX_PROVIDERS, AI_SETUP_MODEL_SOURCES, AI_SETUP_STEPS, AI_SETUP_TEST_OUTCOMES, AI_SETUP_TEST_STATUSES, type AiSetupBackend, type AiSetupModel, type AiSetupModelTest, type AiSetupProvider, type AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import { isArray, isBoolean, isFiniteNumber, isNonEmptyString, isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const INVALID = Symbol('invalid');

type Decoded<T> = T | typeof INVALID;

const readLiteral = <T extends string>(values: readonly T[], value: JsonValue | undefined): Decoded<T> => values.find((entry) => entry === value) ?? INVALID;

const readIdentifier = (value: JsonValue | undefined): Decoded<string> => (isNonEmptyString(value) ? value : INVALID);

const readNullableIdentifier = (value: JsonValue | undefined): Decoded<string | null> => (value === null ? null : readIdentifier(value));

const readFlag = (value: JsonValue | undefined): Decoded<boolean> => (isBoolean(value) ? value : INVALID);

const readList = <T>(value: JsonValue | undefined, limit: number, readEntry: (entry: JsonValue) => Decoded<T>): Decoded<T[]> => {
    if (!isArray(value) || value.length > limit) return INVALID;
    const entries: T[] = [];
    for (const entry of value) {
        const decoded = readEntry(entry);
        if (decoded === INVALID) return INVALID;
        entries.push(decoded);
    }
    return entries;
};

const readBackend = (value: JsonValue): Decoded<AiSetupBackend> => {
    if (!isObject(value)) return INVALID;
    const pluginName = readIdentifier(value['plugin_name']);
    const variantId = readIdentifier(value['variant_id']);
    const taskId = readNullableIdentifier(value['task_id']);
    const excluded = readFlag(value['excluded']);
    if (pluginName === INVALID || variantId === INVALID || taskId === INVALID || excluded === INVALID) return INVALID;
    return { pluginName, variantId, taskId, excluded };
};

const readProvider = (value: JsonValue): Decoded<AiSetupProvider> => {
    if (!isObject(value)) return INVALID;
    const providerId = readIdentifier(value['provider_id']);
    const providerName = readIdentifier(value['provider_name']);
    const pluginName = readIdentifier(value['plugin_name']);
    const excluded = readFlag(value['excluded']);
    if (providerId === INVALID || providerName === INVALID || pluginName === INVALID || excluded === INVALID) return INVALID;
    return { providerId, providerName, pluginName, excluded };
};

const readTest = (value: JsonValue | undefined): Decoded<AiSetupModelTest> => {
    if (!isObject(value)) return INVALID;
    const status = readLiteral(AI_SETUP_TEST_STATUSES, value['status']);
    const outcome = value['outcome'] === null ? null : readLiteral(AI_SETUP_TEST_OUTCOMES, value['outcome']);
    const configurationFingerprint = readNullableIdentifier(value['configuration_fingerprint']);
    const testedAtValue = value['tested_at_ms'];
    const testedAtMs = testedAtValue === null ? null : isFiniteNumber(testedAtValue) && testedAtValue >= 0 ? testedAtValue : INVALID;
    if (status === INVALID || outcome === INVALID || configurationFingerprint === INVALID || testedAtMs === INVALID) return INVALID;
    const outcomeMatchesStatus = status === 'not_run' ? outcome === null : status === 'passed' || status === 'stale' ? outcome === 'passed' : outcome !== null && outcome !== 'passed';
    return outcomeMatchesStatus ? { status, outcome, configurationFingerprint, testedAtMs } : INVALID;
};

const readModel = (value: JsonValue): Decoded<AiSetupModel> => {
    if (!isObject(value)) return INVALID;
    const itemId = readIdentifier(value['item_id']);
    const source = readLiteral(AI_SETUP_MODEL_SOURCES, value['source']);
    const pluginName = readIdentifier(value['plugin_name']);
    const catalogId = readNullableIdentifier(value['catalog_id']);
    const repositoryId = readNullableIdentifier(value['repository_id']);
    const artifactReference = readNullableIdentifier(value['artifact_reference']);
    const artifactName = readNullableIdentifier(value['artifact_name']);
    const modelId = readNullableIdentifier(value['model_id']);
    const downloadTaskId = readNullableIdentifier(value['download_task_id']);
    const test = readTest(value['test']);
    const excluded = readFlag(value['excluded']);
    if (itemId === INVALID || source === INVALID || pluginName === INVALID || catalogId === INVALID || repositoryId === INVALID || artifactReference === INVALID || artifactName === INVALID || modelId === INVALID || downloadTaskId === INVALID || test === INVALID || excluded === INVALID) return INVALID;
    return { itemId, source, pluginName, catalogId, repositoryId, artifactReference, artifactName, modelId, downloadTaskId, test, excluded };
};

const hasConsistentReferences = (state: AiSetupState): boolean => {
    const itemIds = new Set(state.models.map((model) => model.itemId));
    if (itemIds.size !== state.models.length) return false;
    const references = [state.firstChatItemId, state.handoff.itemId, ...state.pendingToastShownFor];
    if (!references.every((itemId) => itemId === null || itemIds.has(itemId))) return false;
    if (new Set(state.pendingToastShownFor).size !== state.pendingToastShownFor.length) return false;
    return !state.handoff.pending || state.handoff.itemId !== null;
};

const decodeAiSetupState = (value: JsonValue | undefined): AiSetupState | null => {
    if (!isObject(value)) return null;
    const sources = value['sources'];
    const engine = value['engine'];
    const handoff = value['handoff'];
    if (!isObject(sources) || !isObject(engine) || !isObject(handoff)) return null;
    const disposition = readLiteral(AI_SETUP_DISPOSITIONS, value['disposition']);
    const step = readLiteral(AI_SETUP_STEPS, value['step']);
    const local = readFlag(sources['local']);
    const cloud = readFlag(sources['cloud']);
    const mode = readLiteral(AI_SETUP_ENGINE_MODES, engine['mode']);
    const backends = readList(engine['backends'], AI_SETUP_MAX_BACKENDS, readBackend);
    const providers = readList(value['providers'], AI_SETUP_MAX_PROVIDERS, readProvider);
    const models = readList(value['models'], AI_SETUP_MAX_MODELS, readModel);
    const firstChatItemId = readNullableIdentifier(value['first_chat_item_id']);
    const pending = readFlag(handoff['pending']);
    const handoffItemId = readNullableIdentifier(handoff['item_id']);
    const pendingToastShownFor = readList(value['pending_toast_shown_for'], AI_SETUP_MAX_MODELS, readIdentifier);
    if (disposition === INVALID || step === INVALID || local === INVALID || cloud === INVALID || mode === INVALID || backends === INVALID || providers === INVALID || models === INVALID || firstChatItemId === INVALID || pending === INVALID || handoffItemId === INVALID || pendingToastShownFor === INVALID) return null;
    const state: AiSetupState = { disposition, step, sources: { local, cloud }, engine: { mode, backends }, providers, models, firstChatItemId, handoff: { pending, itemId: handoffItemId }, pendingToastShownFor };
    return hasConsistentReferences(state) ? state : null;
};

const serializeAiSetupModel = (model: AiSetupModel): JsonObject => ({
    'item_id': model.itemId,
    source: model.source,
    'plugin_name': model.pluginName,
    'catalog_id': model.catalogId,
    'repository_id': model.repositoryId,
    'artifact_reference': model.artifactReference,
    'artifact_name': model.artifactName,
    'model_id': model.modelId,
    'download_task_id': model.downloadTaskId,
    test: { status: model.test.status, outcome: model.test.outcome, 'configuration_fingerprint': model.test.configurationFingerprint, 'tested_at_ms': model.test.testedAtMs },
    excluded: model.excluded
});

const serializeAiSetupState = (state: AiSetupState | null): JsonObject | null => {
    if (!state) return null;
    return {
        disposition: state.disposition,
        step: state.step,
        sources: { local: state.sources.local, cloud: state.sources.cloud },
        engine: { mode: state.engine.mode, backends: state.engine.backends.map((backend) => ({ 'plugin_name': backend.pluginName, 'variant_id': backend.variantId, 'task_id': backend.taskId, excluded: backend.excluded })) },
        providers: state.providers.map((provider) => ({ 'provider_id': provider.providerId, 'provider_name': provider.providerName, 'plugin_name': provider.pluginName, excluded: provider.excluded })),
        models: state.models.map(serializeAiSetupModel),
        'first_chat_item_id': state.firstChatItemId,
        handoff: { pending: state.handoff.pending, 'item_id': state.handoff.itemId },
        'pending_toast_shown_for': [...state.pendingToastShownFor]
    };
};

export { decodeAiSetupState, serializeAiSetupState };
