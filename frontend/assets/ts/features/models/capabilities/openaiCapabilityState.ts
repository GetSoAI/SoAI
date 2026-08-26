/* SoAI - Models feature OpenAI capability state [frontend/assets/ts/features/models/capabilities/openaiCapabilityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeOpenAICapabilityToken } from '@core/openai/capabilityChecks.ts';
import { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken, type OpenAICapabilityOverrideCategory } from '@core/openai/capabilityCategories.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type OpenAICapabilityDisabledMap = Map<OpenAICapabilityOverrideCategory, ReadonlySet<string>>;

interface OpenAICapabilityOverrideState {
    modelId: string;
    originalDisabled: OpenAICapabilityDisabledMap;
    currentDisabled: OpenAICapabilityDisabledMap;
}

interface OpenAICapabilityOverrideSaveOperation {
    category: OpenAICapabilityOverrideCategory;
    token: string;
    enabled: boolean;
}

interface OpenAICapabilityOverrideApi {
    updateOpenAICapabilityOverride: (modelId: string, payload: OpenAICapabilityOverrideSaveOperation) => Promise<SuccessfulMutationResponse>;
    resetOpenAICapabilityOverrides: (modelId: string) => Promise<SuccessfulMutationResponse>;
}

const normalizeOverrideToken = (value: string): string => normalizeOpenAICapabilityToken(value);

const extractOpenAICapabilityDisabledMap = (overrides: JsonValue | undefined): OpenAICapabilityDisabledMap => {
    const result: OpenAICapabilityDisabledMap = new Map();
    if (!isJsonObject(overrides)) {
        return result;
    }
    const disabledRaw = overrides['disabled'];
    if (!isJsonObject(disabledRaw)) {
        return result;
    }
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const tokens = filterStringArrayValue(disabledRaw[category])
            .map((entry) => normalizeOverrideToken(entry))
            .filter((token: string): boolean => Boolean(token) && isSafeOpenAICapabilityToken(token));
        if (tokens.length) {
            result.set(category, new Set(tokens));
        }
    }
    return result;
};

const cloneOpenAICapabilityDisabledMap = (source: OpenAICapabilityDisabledMap): OpenAICapabilityDisabledMap => {
    const cloned: OpenAICapabilityDisabledMap = new Map();
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const tokens = source.get(category);
        if (tokens?.size) {
            cloned.set(category, new Set(tokens));
        }
    }
    return cloned;
};

const isOpenAICapabilityDisabled = (source: OpenAICapabilityDisabledMap, category: OpenAICapabilityOverrideCategory, token: string): boolean => source.get(category)?.has(normalizeOverrideToken(token)) === true;

const buildOpenAICapabilityOverridesPayload = (source: OpenAICapabilityDisabledMap): JsonObject | null => {
    const disabled: JsonObject = {};
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const tokens = source.get(category);
        if (tokens?.size) {
            disabled[category] = Array.from(tokens).sort((left, right) => left.localeCompare(right, 'en'));
        }
    }
    return Object.keys(disabled).length ? { disabled } : null;
};

const serializeOpenAICapabilityDisabledMap = (source: OpenAICapabilityDisabledMap): string => JSON.stringify(buildOpenAICapabilityOverridesPayload(source));

const createOpenAICapabilityOverrideState = (model: ModelRecord, modelId: string): OpenAICapabilityOverrideState => {
    const originalDisabled = extractOpenAICapabilityDisabledMap(model.openaiCapabilitiesOverrides);
    return {
        modelId,
        originalDisabled,
        currentDisabled: cloneOpenAICapabilityDisabledMap(originalDisabled)
    };
};

const hasOpenAICapabilityOverrideChanges = (state: OpenAICapabilityOverrideState | null): boolean => {
    return Boolean(state && serializeOpenAICapabilityDisabledMap(state.originalDisabled) !== serializeOpenAICapabilityDisabledMap(state.currentDisabled));
};

const setOpenAICapabilityOverrideEnabled = (state: OpenAICapabilityOverrideState, category: OpenAICapabilityOverrideCategory, token: string, enabled: boolean): void => {
    const normalizedToken = normalizeOverrideToken(token);
    if (!isSafeOpenAICapabilityToken(normalizedToken)) {
        throw new Error('OpenAI capability override token is invalid');
    }
    const next = cloneOpenAICapabilityDisabledMap(state.currentDisabled);
    const tokens = new Set(next.get(category) ?? []);
    if (enabled) {
        tokens.delete(normalizedToken);
    } else {
        tokens.add(normalizedToken);
    }
    if (tokens.size) {
        next.set(category, tokens);
    } else {
        next.delete(category);
    }
    state.currentDisabled = next;
};

const resetOpenAICapabilityOverrideState = (state: OpenAICapabilityOverrideState): void => {
    state.currentDisabled = new Map();
};

const getOpenAICapabilityOverrideSaveOperations = (state: OpenAICapabilityOverrideState): OpenAICapabilityOverrideSaveOperation[] => {
    const operations: OpenAICapabilityOverrideSaveOperation[] = [];
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const tokens = new Set<string>([...(state.originalDisabled.get(category) ?? []), ...(state.currentDisabled.get(category) ?? [])]);
        for (const token of Array.from(tokens).sort((left, right) => left.localeCompare(right, 'en'))) {
            const originalDisabled = state.originalDisabled.get(category)?.has(token) === true;
            const currentDisabled = state.currentDisabled.get(category)?.has(token) === true;
            if (originalDisabled !== currentDisabled) {
                operations.push({ category, token, enabled: !currentDisabled });
            }
        }
    }
    return operations;
};

const applyOpenAICapabilityOverrideStateToModel = (model: ModelRecord, state: OpenAICapabilityOverrideState): ModelRecord => ({
    ...model,
    openaiCapabilitiesOverrides: buildOpenAICapabilityOverridesPayload(state.currentDisabled)
});

const applyOpenAICapabilityEffectiveToggle = (model: ModelRecord, category: OpenAICapabilityOverrideCategory, token: string, enabled: boolean): ModelRecord => {
    let updatedModel = model;
    const openaiValue = model.openaiCapabilities;
    if (isJsonObject(openaiValue)) {
        let updatedOpenAI = openaiValue;
        if (token in openaiValue) {
            updatedOpenAI = { ...updatedOpenAI, [token]: enabled };
        }
        const sectionValue = openaiValue[category];
        if (isJsonObject(sectionValue) && token in sectionValue) {
            updatedOpenAI = { ...updatedOpenAI, [category]: { ...sectionValue, [token]: enabled } };
        }
        updatedModel = { ...updatedModel, openaiCapabilities: updatedOpenAI };
    }
    if (category === 'modalities') {
        const normalized = filterStringArrayValue(updatedModel.modalities)
            .map((entry) => normalizeOverrideToken(entry))
            .filter((entry: string): boolean => Boolean(entry));
        const updated = new Set(normalized);
        updated.add('text');
        if (enabled) {
            updated.add(token);
        } else if (token !== 'text') {
            updated.delete(token);
        }
        updatedModel = { ...updatedModel, modalities: Array.from(updated) };
        if (!enabled && token === 'vision') {
            updatedModel = applyOpenAICapabilityEffectiveToggle(updatedModel, 'chat_features', 'vision', false);
        }
        if (!enabled && token === 'audio') {
            updatedModel = applyOpenAICapabilityEffectiveToggle(updatedModel, 'chat_features', 'input_audio', false);
        }
    }
    if (!enabled && category === 'endpoints' && token === 'images') {
        updatedModel = applyOpenAICapabilityEffectiveToggle(updatedModel, 'image_features', 'image_edits', false);
        updatedModel = applyOpenAICapabilityEffectiveToggle(updatedModel, 'image_features', 'image_variations', false);
    }
    return updatedModel;
};

const commitOpenAICapabilityOverrideState = (state: OpenAICapabilityOverrideState): void => {
    state.originalDisabled = cloneOpenAICapabilityDisabledMap(state.currentDisabled);
};

const saveOpenAICapabilityOverrideState = async (dependencies: { api: OpenAICapabilityOverrideApi; model: ModelRecord; state: OpenAICapabilityOverrideState }): Promise<ModelRecord> => {
    const { api, model, state } = dependencies;
    if (!hasOpenAICapabilityOverrideChanges(state)) {
        return model;
    }
    const operations = getOpenAICapabilityOverrideSaveOperations(state);
    if (!buildOpenAICapabilityOverridesPayload(state.currentDisabled)) {
        await api.resetOpenAICapabilityOverrides(state.modelId);
    } else {
        for (const operation of operations) {
            await api.updateOpenAICapabilityOverride(state.modelId, operation);
        }
    }
    let updatedModel = model;
    for (const operation of operations) {
        updatedModel = applyOpenAICapabilityEffectiveToggle(updatedModel, operation.category, operation.token, operation.enabled);
    }
    updatedModel = applyOpenAICapabilityOverrideStateToModel(updatedModel, state);
    commitOpenAICapabilityOverrideState(state);
    return updatedModel;
};

export { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, createOpenAICapabilityOverrideState, getOpenAICapabilityOverrideSaveOperations, hasOpenAICapabilityOverrideChanges, isOpenAICapabilityDisabled, isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken, normalizeOverrideToken, resetOpenAICapabilityOverrideState, saveOpenAICapabilityOverrideState, setOpenAICapabilityOverrideEnabled };
export type { OpenAICapabilityDisabledMap, OpenAICapabilityOverrideApi, OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideSaveOperation, OpenAICapabilityOverrideState };
