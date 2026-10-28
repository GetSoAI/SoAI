/* SoAI - Models feature OpenAI capability state [frontend/assets/ts/features/models/capabilities/openaiCapabilityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { normalizeOpenAICapabilityToken } from '@core/openai/capabilityChecks.ts';
import { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, isOpenAICapabilityOverrideCategory, isSafeOpenAICapabilityToken, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideReplaceRequest, type OpenAICapabilityOverrideSet } from '@core/openai/capabilityCategories.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type OpenAICapabilityOverrideMode = 'auto' | 'enabled' | 'disabled';
type OpenAICapabilityExplicitMode = Exclude<OpenAICapabilityOverrideMode, 'auto'>;
type OpenAICapabilityOverrideMap = ReadonlyMap<OpenAICapabilityOverrideCategory, ReadonlyMap<string, OpenAICapabilityExplicitMode>>;

interface OpenAICapabilityOverrideState {
    modelId: string;
    original: OpenAICapabilityOverrideMap;
    current: OpenAICapabilityOverrideMap;
}

interface OpenAICapabilityOverrideApi {
    replaceOpenAICapabilityOverrides: (modelId: string, payload: OpenAICapabilityOverrideReplaceRequest) => Promise<SuccessfulMutationResponse>;
}

const OPENAI_CAPABILITY_OVERRIDE_MODES: readonly OpenAICapabilityOverrideMode[] = ['auto', 'enabled', 'disabled'];

const isOpenAICapabilityOverrideMode = (value: string): value is OpenAICapabilityOverrideMode => value === 'auto' || value === 'enabled' || value === 'disabled';

const normalizeOverrideToken = (value: string): string => normalizeOpenAICapabilityToken(value);

const readOverrideTokens = (section: JsonValue | undefined, category: OpenAICapabilityOverrideCategory): string[] => {
    if (!isJsonObject(section)) {
        return [];
    }
    return filterStringArrayValue(section[category])
        .map((entry) => normalizeOverrideToken(entry))
        .filter((token: string): boolean => Boolean(token) && isSafeOpenAICapabilityToken(token));
};

const extractOpenAICapabilityOverrideMap = (overrides: JsonValue | null | undefined): OpenAICapabilityOverrideMap => {
    const result = new Map<OpenAICapabilityOverrideCategory, ReadonlyMap<string, OpenAICapabilityExplicitMode>>();
    if (!isJsonObject(overrides)) {
        return result;
    }
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const modes = new Map<string, OpenAICapabilityExplicitMode>();
        for (const token of readOverrideTokens(overrides['enabled'], category)) {
            modes.set(token, 'enabled');
        }
        for (const token of readOverrideTokens(overrides['disabled'], category)) {
            modes.set(token, 'disabled');
        }
        if (modes.size) {
            result.set(category, modes);
        }
    }
    return result;
};

const resolveOpenAICapabilityOverrideMode = (source: OpenAICapabilityOverrideMap, category: OpenAICapabilityOverrideCategory, token: string): OpenAICapabilityOverrideMode => source.get(category)?.get(normalizeOverrideToken(token)) ?? 'auto';

const hasOpenAICapabilityOverrides = (source: OpenAICapabilityOverrideMap): boolean => source.size > 0;

const buildOpenAICapabilityOverrideSet = (source: OpenAICapabilityOverrideMap): OpenAICapabilityOverrideSet => {
    const overrideSet: OpenAICapabilityOverrideSet = { disabled: {}, enabled: {} };
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const modes = source.get(category);
        if (!modes) {
            continue;
        }
        const tokens = Array.from(modes.keys()).sort((left, right) => left.localeCompare(right, 'en'));
        const disabled = tokens.filter((token) => modes.get(token) === 'disabled');
        const enabled = tokens.filter((token) => modes.get(token) === 'enabled');
        if (disabled.length) {
            overrideSet.disabled[category] = disabled;
        }
        if (enabled.length) {
            overrideSet.enabled[category] = enabled;
        }
    }
    return overrideSet;
};

const buildOpenAICapabilityOverridesPayload = (source: OpenAICapabilityOverrideMap): JsonObject | null => {
    const overrideSet = buildOpenAICapabilityOverrideSet(source);
    const payload: JsonObject = {};
    if (Object.keys(overrideSet.disabled).length) {
        payload['disabled'] = { ...overrideSet.disabled };
    }
    if (Object.keys(overrideSet.enabled).length) {
        payload['enabled'] = { ...overrideSet.enabled };
    }
    return Object.keys(payload).length ? payload : null;
};

const serializeOpenAICapabilityOverrideMap = (source: OpenAICapabilityOverrideMap): string => JSON.stringify(buildOpenAICapabilityOverrideSet(source));

const createOpenAICapabilityOverrideState = (model: ModelRecord, modelId: string): OpenAICapabilityOverrideState => {
    const original = extractOpenAICapabilityOverrideMap(model.openaiCapabilitiesOverrides);
    return { modelId, original, current: original };
};

const hasOpenAICapabilityOverrideChanges = (state: OpenAICapabilityOverrideState | null): boolean => {
    return Boolean(state && serializeOpenAICapabilityOverrideMap(state.original) !== serializeOpenAICapabilityOverrideMap(state.current));
};

const setOpenAICapabilityOverrideMode = (state: OpenAICapabilityOverrideState, category: OpenAICapabilityOverrideCategory, token: string, mode: OpenAICapabilityOverrideMode): void => {
    const normalizedToken = normalizeOverrideToken(token);
    if (!isSafeOpenAICapabilityToken(normalizedToken)) {
        throw new Error('OpenAI capability override token is invalid');
    }
    if (category === 'modalities' && normalizedToken === 'text' && mode !== 'auto') {
        throw new Error('The text modality cannot be overridden');
    }
    const next = new Map(state.current);
    const modes = new Map(next.get(category) ?? []);
    if (mode === 'auto') {
        modes.delete(normalizedToken);
    } else {
        modes.set(normalizedToken, mode);
    }
    if (modes.size) {
        next.set(category, modes);
    } else {
        next.delete(category);
    }
    state.current = next;
};

const isOpenAICapabilityOverrideConflict = (error: Error): boolean => error instanceof APIError && error.status === 409;

const discardOpenAICapabilityOverrideChanges = (state: OpenAICapabilityOverrideState): void => {
    state.current = state.original;
};

const resetOpenAICapabilityOverrideState = (state: OpenAICapabilityOverrideState): void => {
    state.current = new Map();
};

const saveOpenAICapabilityOverrideState = async (dependencies: { api: OpenAICapabilityOverrideApi; model: ModelRecord; state: OpenAICapabilityOverrideState }): Promise<ModelRecord> => {
    const { api, model, state } = dependencies;
    if (!hasOpenAICapabilityOverrideChanges(state)) {
        return model;
    }
    const submitted: OpenAICapabilityOverrideState = { ...state };
    await api.replaceOpenAICapabilityOverrides(state.modelId, {
        overrides: buildOpenAICapabilityOverrideSet(submitted.current),
        expected: buildOpenAICapabilityOverrideSet(submitted.original)
    });
    state.original = submitted.current;
    return { ...model, openaiCapabilitiesOverrides: buildOpenAICapabilityOverridesPayload(submitted.current), openaiBaseProfile: null };
};

export { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES, OPENAI_CAPABILITY_OVERRIDE_MODES, createOpenAICapabilityOverrideState, discardOpenAICapabilityOverrideChanges, hasOpenAICapabilityOverrideChanges, hasOpenAICapabilityOverrides, isOpenAICapabilityOverrideCategory, isOpenAICapabilityOverrideConflict, isOpenAICapabilityOverrideMode, isSafeOpenAICapabilityToken, normalizeOverrideToken, resetOpenAICapabilityOverrideState, resolveOpenAICapabilityOverrideMode, saveOpenAICapabilityOverrideState, setOpenAICapabilityOverrideMode };
export type { OpenAICapabilityOverrideApi, OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideMap, OpenAICapabilityOverrideMode, OpenAICapabilityOverrideReplaceRequest, OpenAICapabilityOverrideSet, OpenAICapabilityOverrideState };
