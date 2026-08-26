/* SoAI - Shared models model record normalization [frontend/assets/ts/core/models/modelRecordNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedLower, toTrimmedString, toTrimmedStringOrNull, toTrimmedUpper } from '@core/normalize.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import type { ModelData, ModelRecord } from '@core/types/modelTypes.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { decodeModelRecord } from '@core/models/modelRecordBoundary.ts';

interface ProviderDetails {
    name: string;
    metadata: JsonValue;
}

type NormalizedModelRecord = ModelRecord & {
    plugin: string;
    provider: string;
    providerMetadata: JsonValue;
    pluginStatus: string;
    status: string;
    available: boolean;
    loaded: boolean;
};

interface ResolveIdParameters {
    rawUniversalId: string | undefined;
    baseId: string | undefined;
    type: string | undefined;
}

const toNullableString = toTrimmedStringOrNull;

const normalizeProviderDetails = (provider: JsonValue | undefined, fallbackName = ''): ProviderDetails => {
    if (isJsonObject(provider)) {
        const id = toTrimmedString(provider['id']);
        const name = toTrimmedString(provider['name']) || id || fallbackName;
        return {
            name,
            metadata: provider
        };
    }
    const name = toTrimmedString(provider) || fallbackName;
    return {
        name,
        metadata: null
    };
};

const normalizeStatusValue = (value: JsonValue | undefined, fallback = ''): string => {
    if (!isString(value)) return fallback;
    const normalized = toTrimmedUpper(value);
    return normalized || fallback;
};

const resolveModelUniversalId = ({ rawUniversalId, baseId, type }: ResolveIdParameters): string | undefined => {
    const raw = toTrimmedString(rawUniversalId);
    if (raw) return raw;
    if (type === 'virtual') return toTrimmedString(baseId) || undefined;
    return undefined;
};

const resolveModelVisibleName = (inputArguments: { displayName: string; sourceModelId: string; modelId: string; name: string; id: string; universalId: string }): string => {
    const displayName = inputArguments.displayName && inputArguments.displayName !== inputArguments.universalId ? inputArguments.displayName : '';
    return displayName || inputArguments.sourceModelId || inputArguments.modelId || inputArguments.name || inputArguments.id || inputArguments.universalId;
};

const normalizeModelRecord = (model: JsonValue): NormalizedModelRecord | null => {
    if (!isJsonObject(model)) return null;
    const pluginName = toTrimmedString(model['plugin']) || toTrimmedString(model['pluginName']);
    const providerSource = model['provider'] ?? model['providerName'];
    const isVirtualModel = model['type'] === 'virtual';
    const providerDetails = normalizeProviderDetails(providerSource, pluginName || (isVirtualModel ? 'virtual' : ''));
    const providerMetadata = providerDetails.metadata ?? (isJsonObject(model['providerMetadata']) ? model['providerMetadata'] : null);
    const resolvedPlugin = pluginName || (isVirtualModel ? 'virtual' : providerDetails.name);
    const resolvedProvider = providerDetails.name || resolvedPlugin;
    const baseId = toTrimmedString(model['id']) || toTrimmedString(model['name']) || toTrimmedString(model['sourceModelId']) || toTrimmedString(model['modelId']);
    const universalId = resolveModelUniversalId({
        rawUniversalId: toTrimmedString(model['universalId']),
        baseId,
        type: toTrimmedString(model['type']) || undefined
    });
    const normalized: NormalizedModelRecord = {
        ...model,
        plugin: resolvedPlugin,
        provider: resolvedProvider,
        providerMetadata,
        pluginStatus: normalizeStatusValue(model['pluginStatus'] ?? model['state'], isVirtualModel ? 'PERSISTENT_READY' : 'UNKNOWN'),
        status: toTrimmedLower(model['status']),
        available: isVirtualModel ? true : Boolean(model['isAvailable']),
        loaded: isVirtualModel ? true : Boolean(model['isLoaded'])
    };
    if (universalId) normalized.universalId = universalId;
    return normalized;
};

const normalizeGroupedModelCollection = (payload: JsonValue, locale: string): ModelData[] => {
    if (!isJsonObject(payload)) {
        return [];
    }
    const all: ModelData[] = [];
    for (const [groupName, groupValue] of Object.entries(payload)) {
        if (!isJsonArray(groupValue)) {
            continue;
        }
        for (const candidate of groupValue) {
            if (!isJsonObject(candidate)) {
                continue;
            }
            const decodedCandidate = decodeModelRecord(candidate);
            const modelType = toTrimmedString(decodedCandidate.type) || 'local';
            const type = groupName === 'virtual' ? 'virtual' : modelType;
            const universalId = toTrimmedString(decodedCandidate.universalId) || (type === 'virtual' ? toTrimmedString(decodedCandidate.id) || toTrimmedString(decodedCandidate.name) : '');
            if (!universalId) {
                continue;
            }
            const id = toTrimmedString(decodedCandidate.id) || toTrimmedString(decodedCandidate.modelId) || toTrimmedString(decodedCandidate.sourceModelId) || toTrimmedString(decodedCandidate.name) || universalId;
            if (!id) {
                continue;
            }
            const sourceModelId = toTrimmedString(decodedCandidate.sourceModelId);
            const modelId = toTrimmedString(decodedCandidate.modelId);
            const displayName = toTrimmedString(decodedCandidate.displayName);
            const name = resolveModelVisibleName({
                displayName,
                sourceModelId,
                modelId,
                name: toTrimmedString(decodedCandidate.name),
                id: toTrimmedString(decodedCandidate.id) || id,
                universalId: universalId
            });
            const providerRaw = decodedCandidate.provider;
            const providerName = isJsonObject(providerRaw) && isString(providerRaw['name']) ? providerRaw['name'] : providerRaw;
            const provider = toTrimmedString(providerName) || toTrimmedString(decodedCandidate.plugin) || groupName;
            const plugin = toTrimmedString(decodedCandidate.plugin) || (type === 'virtual' ? 'virtual' : groupName);
            const loaded = type === 'virtual' || decodedCandidate.isLoaded === true;
            const available = type === 'virtual' || decodedCandidate.isAvailable === true;
            all.push({
                ...decodedCandidate,
                id,
                name,
                type,
                universalId,
                displayName: name,
                provider,
                plugin,
                loaded,
                available
            });
        }
    }
    return all.sort((firstValue, secondValue) => (firstValue.displayName || '').localeCompare(secondValue.displayName || '', locale));
};

const normalizeFormattedModelListPayload = (payload: JsonValue, locale: string): ModelData[] | null => {
    const normalizeEntries = (entries: readonly JsonValue[]): ModelData[] => entries.map(normalizeModelPayloadEntry).filter((model): model is ModelData => model !== null);
    if (isJsonArray(payload)) {
        return normalizeEntries(payload);
    }
    if (isJsonObject(payload)) {
        return normalizeGroupedModelCollection(payload, locale);
    }
    return null;
};

const normalizeModelPayloadEntry = (entry: JsonValue): ModelData | null => {
    if (!isJsonObject(entry)) return null;
    const decodedEntry = decodeModelRecord(entry);
    const idValue = decodedEntry.id;
    if (!isString(idValue) || !idValue.trim()) return null;
    const normalizedType = toTrimmedString(decodedEntry.type);
    const isVirtualModel = normalizedType === 'virtual';
    const resolvedType = normalizedType || (isVirtualModel ? 'virtual' : 'local');
    const universalId = toTrimmedString(decodedEntry.universalId);
    const modelId = idValue.trim();
    const canonicalId = isVirtualModel ? modelId : universalId;
    if (!canonicalId) return null;
    const displayName = toTrimmedString(decodedEntry.displayName);
    const sourceModelId = toTrimmedString(decodedEntry.sourceModelId);
    const entryModelId = toTrimmedString(decodedEntry.modelId);
    const resolvedName = resolveModelVisibleName({
        displayName: displayName,
        sourceModelId: sourceModelId,
        modelId: entryModelId,
        name: toTrimmedString(decodedEntry.name),
        id: modelId,
        universalId: universalId
    });
    const plugin = toTrimmedString(decodedEntry.plugin);
    const providerDetails = normalizeProviderDetails(decodedEntry.provider, plugin || (isVirtualModel ? 'virtual' : ''));
    const provider = providerDetails.name || plugin || (isVirtualModel ? 'virtual' : '');
    const result: ModelData = {
        ...decodedEntry,
        id: canonicalId,
        name: resolvedName,
        provider,
        loaded: decodedEntry.isLoaded === true,
        available: isVirtualModel || decodedEntry.isAvailable === true
    };
    result.modelId = entryModelId || modelId;
    const providerMetadata = providerDetails.metadata ?? decodedEntry.providerMetadata ?? null;
    if (providerMetadata !== null) result.providerMetadata = providerMetadata;
    if (sourceModelId) result.sourceModelId = sourceModelId;
    const rawUpstreamModelId = toTrimmedString(decodedEntry.rawUpstreamModelId);
    if (rawUpstreamModelId) result.rawUpstreamModelId = rawUpstreamModelId;
    if (universalId) result.universalId = universalId;
    result.type = resolvedType;
    const contextWindowTokens = decodedEntry.contextWindowTokens;
    if (isNumber(contextWindowTokens) && Number.isFinite(contextWindowTokens) && contextWindowTokens > 0) {
        result.contextWindowTokens = Math.floor(contextWindowTokens);
    }
    if (resolvedName) result.displayName = resolvedName;
    if (plugin) result.plugin = plugin;
    if (decodedEntry.isLoaded !== undefined) result.isLoaded = decodedEntry.isLoaded;
    if (decodedEntry.isAvailable !== undefined) result.isAvailable = decodedEntry.isAvailable;
    const status = toTrimmedString(decodedEntry.status);
    if (status) result.status = status;
    const pluginStatus = toTrimmedString(decodedEntry.pluginStatus);
    if (pluginStatus) result.pluginStatus = pluginStatus;
    if (decodedEntry.isOrphaned !== undefined) result.isOrphaned = decodedEntry.isOrphaned;
    return result;
};

const resolveModelDisplayName = (modelIndex: Map<string, ModelData>, modelId: string | null | undefined): string => {
    if (!modelId) return '';
    const model = modelIndex.get(modelId);
    if (model && isString(model.displayName) && model.displayName.trim() && model.displayName.trim() !== toTrimmedString(model.universalId)) return model.displayName.trim();
    if (model && isString(model.sourceModelId) && model.sourceModelId.trim()) return model.sourceModelId.trim();
    if (model && isString(model.modelId) && model.modelId.trim()) return model.modelId.trim();
    if (model && isString(model.name) && model.name.trim()) return model.name.trim();
    if (model && isString(model.id) && model.id.trim()) return model.id.trim();
    return modelId;
};

export { normalizeFormattedModelListPayload, normalizeGroupedModelCollection, normalizeModelPayloadEntry, normalizeModelRecord, normalizeStatusValue, resolveModelDisplayName, toNullableString };
