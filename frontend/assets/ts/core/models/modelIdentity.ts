/* SoAI - Shared models model identity [frontend/assets/ts/core/models/modelIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const extractCleanModelId = (modelId: JsonValue | undefined): string => {
    const normalizedModelId = toTrimmedString(modelId);
    const lastSegment = normalizedModelId.split('/').pop();
    return lastSegment || normalizedModelId;
};

const resolveModelProviderMetadataName = (model: ModelRecord): string => {
    const provider = model.provider;
    if (isJsonObject(provider)) {
        const name = toTrimmedString(provider['name']);
        if (name) return name;
    }
    const providerMetadata = model.providerMetadata;
    if (isJsonObject(providerMetadata)) {
        const name = toTrimmedString(providerMetadata['name']);
        if (name) return name;
    }
    return '';
};

const resolveModelPluginName = (model: ModelRecord): string => {
    const plugin = toTrimmedString(model.plugin) || toTrimmedString(model.pluginName);
    if (plugin) return plugin;
    if (model.type === 'virtual') return 'virtual';
    const provider = toTrimmedString(model.provider) || toTrimmedString(model.providerName);
    if (provider) return provider;
    const providerMetadata = model.providerMetadata;
    if (isJsonObject(providerMetadata)) {
        const name = toTrimmedString(providerMetadata['name']);
        if (name) return name;
    }
    return '';
};

const resolveModelProviderName = (model: ModelRecord): string => {
    const providerMetadataName = resolveModelProviderMetadataName(model);
    if (providerMetadataName) return providerMetadataName;
    const provider = toTrimmedString(model.provider) || toTrimmedString(model.providerName);
    if (provider) return provider;
    return resolveModelPluginName(model);
};

const resolveModelOriginId = (model: ModelRecord): string => {
    return toTrimmedString(model.rawUpstreamModelId) || toTrimmedString(model.sourceModelId) || toTrimmedString(model.modelId) || toTrimmedString(model.name) || toTrimmedString(model.id) || '';
};

const resolveModelSourceName = (model: ModelRecord): string => {
    return resolveModelOriginId(model) || toTrimmedString(model.universalId);
};

const resolveOpenAiEndpointModelId = (model: ModelRecord): string => {
    if (model.type === 'virtual') {
        return toTrimmedString(model.id) || toTrimmedString(model.name);
    }
    const plugin = resolveModelPluginName(model);
    const sourceModelId = toTrimmedString(model.sourceModelId) || toTrimmedString(model.rawUpstreamModelId) || toTrimmedString(model.modelId);
    if (plugin && sourceModelId) {
        return sourceModelId.startsWith(`${plugin}/`) ? sourceModelId : `${plugin}/${sourceModelId}`;
    }
    return toTrimmedString(model.modelId) || toTrimmedString(model.id) || '';
};

const appendUniqueModelIdentityCandidate = (candidates: string[], seen: Set<string>, value: JsonValue | undefined): void => {
    const candidate = toTrimmedString(value);
    if (!candidate || seen.has(candidate)) {
        return;
    }
    seen.add(candidate);
    candidates.push(candidate);
};

const resolveModelIdentityCandidates = (model: ModelRecord): string[] => {
    const candidates: string[] = [];
    const seen = new Set<string>();
    appendUniqueModelIdentityCandidate(candidates, seen, model.id);
    appendUniqueModelIdentityCandidate(candidates, seen, model.universalId);
    appendUniqueModelIdentityCandidate(candidates, seen, model.modelId);
    appendUniqueModelIdentityCandidate(candidates, seen, model.sourceModelId);
    appendUniqueModelIdentityCandidate(candidates, seen, model.rawUpstreamModelId);
    appendUniqueModelIdentityCandidate(candidates, seen, model.name);
    appendUniqueModelIdentityCandidate(candidates, seen, model.displayName);
    appendUniqueModelIdentityCandidate(candidates, seen, model.alias);
    appendUniqueModelIdentityCandidate(candidates, seen, resolveOpenAiEndpointModelId(model));
    return candidates;
};

const resolveModelDisplayName = (model: ModelRecord): string => {
    const aliasName = toTrimmedString(model.alias) || toTrimmedString(model.displayName);
    const originId = resolveModelOriginId(model);
    const cleanOrigin = originId ? extractCleanModelId(originId) : '';
    const fallbackName = toTrimmedString(model.name) || toTrimmedString(model.id);
    if (model.hasAlias === true) {
        return aliasName || cleanOrigin || fallbackName || '';
    }
    return cleanOrigin || fallbackName || aliasName || '';
};

const resolveModelItemCardId = (model: ModelRecord): string => {
    const universalId = toTrimmedString(model.universalId);
    if (universalId) return universalId;
    const base = toTrimmedString(model.id) || toTrimmedString(model.name);
    if (model.type === 'virtual') return base;
    const provider = resolveModelProviderName(model);
    return provider && base ? `${provider}-${base}` : base;
};

export { extractCleanModelId, resolveModelDisplayName, resolveModelIdentityCandidates, resolveModelItemCardId, resolveModelOriginId, resolveModelPluginName, resolveModelProviderName, resolveModelSourceName, resolveOpenAiEndpointModelId };
