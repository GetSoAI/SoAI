/* SoAI - Shared search result normalization [frontend/assets/ts/core/search/searchResultNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { formatPositiveEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { buildCpuDeviceResult, buildGpuDeviceResult, buildNetworkDeviceResult, buildVolumeDeviceResult } from '@core/search/searchDeviceItems.ts';
import type { SearchResultConversationResponse, SearchResultDeviceResponse, SearchResultModelResponse, SearchResultPluginResponse, SearchResultPromptResponse, SearchResultsResponse } from '@core/api/contracts/searchContracts.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isFiniteNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const toSearchIdString = (value: JsonValue | null | undefined): string | null => {
    if (value === null || value === undefined) return null;
    if (isString(value)) {
        const trimmed = value.trim();
        return trimmed ? trimmed : null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) return String(value);
    return null;
};

const normalizeSearchStatus = (status: JsonValue | null | undefined): string => toTrimmedStringOrNull(status)?.toUpperCase() || 'UNKNOWN';

const formatSearchResultDate = (value: JsonValue | null | undefined): string => (isFiniteNumber(value) ? formatPositiveEpochMsMinuteWithFallback(value, '') : '');

const buildPluginSearchDescription = (versionValue: JsonValue | null | undefined, providerSource: JsonValue | null | undefined, descriptionValue: JsonValue | null | undefined = null): string => {
    const description = toTrimmedStringOrNull(descriptionValue);
    if (description) return description;
    const version = toTrimmedStringOrNull(versionValue);
    const provider = toTrimmedStringOrNull(providerSource);
    if (version && provider) return i18n.t('search.remote.pluginDescriptionVersionProvider', { version, provider });
    if (version) return i18n.t('search.remote.pluginDescriptionVersionOnly', { version });
    if (provider) return i18n.t('search.remote.pluginDescriptionProviderOnly', { provider });
    return i18n.t('search.remote.pluginDescriptionGeneric');
};

const buildModelSearchDescription = (descriptionValue: JsonValue | null | undefined, providerSource: JsonValue | null | undefined): string => {
    const description = toTrimmedStringOrNull(descriptionValue);
    if (description) return description;
    const provider = toTrimmedStringOrNull(providerSource);
    return provider ? i18n.t('search.remote.modelDescriptionProvider', { provider }) : i18n.t('search.remote.modelDescriptionGeneric');
};

const buildConversationSearchDescription = (modifiedValue: JsonValue | null | undefined): string => {
    const modified = formatSearchResultDate(modifiedValue);
    return modified ? i18n.t('search.remote.conversationDescriptionModified', { modified }) : i18n.t('search.remote.conversationDescriptionGeneric');
};

const buildPromptSearchDescription = (modifiedValue: JsonValue | null | undefined): string => {
    const modified = formatSearchResultDate(modifiedValue);
    return modified ? i18n.t('search.remote.promptDescriptionModified', { modified }) : i18n.t('search.remote.promptDescriptionGeneric');
};

const normalizeModelForIndex = (model: JsonValue | null | undefined): SearchItem | null => {
    if (!isJsonObject(model)) return null;
    const modelType = toTrimmedStringOrNull(model['type']);
    const id = toSearchIdString(model['universalId']) || (modelType === 'virtual' ? toSearchIdString(model['id']) || toSearchIdString(model['name']) : null);
    if (!id) return null;
    const displayName = toTrimmedStringOrNull(model['displayName']) || toTrimmedStringOrNull(model['name']);
    if (!displayName) return null;
    const stateValue = model['state'];
    return {
        id,
        name: displayName,
        description: buildModelSearchDescription(model['description'], model['plugin'] ?? model['provider'] ?? model['source']),
        type: 'models',
        category: 'models',
        plugin: toTrimmedStringOrNull(model['plugin']) || '',
        status: stateValue ? String(stateValue).toUpperCase() : model['isLoaded'] === true ? 'LOADED' : model['available'] === true ? 'AVAILABLE' : 'UNKNOWN'
    };
};

const normalizePluginForIndex = (plugin: JsonValue | null | undefined): SearchItem | null => {
    if (!isJsonObject(plugin)) return null;
    const id = toSearchIdString(plugin['name']);
    if (!id) return null;
    const displayName = toTrimmedStringOrNull(plugin['displayName']) || toTrimmedStringOrNull(plugin['name']);
    if (!displayName) return null;
    const stateValue = plugin['state'];
    return {
        id,
        name: displayName,
        description: buildPluginSearchDescription(plugin['versionSoaiplugin'], plugin['provider'] ?? plugin['plugin'] ?? plugin['name'], plugin['descriptionSoaiplugin']),
        type: 'plugins',
        category: 'plugins',
        plugin: toTrimmedStringOrNull(plugin['name']) || '',
        status: stateValue ? String(stateValue).toUpperCase() : plugin['isEnabled'] === true ? 'IDLE' : 'DISABLED'
    };
};

const normalizeRemoteDevice = (device: SearchResultDeviceResponse): SearchItem | null => {
    const component = device.component.trim().toLowerCase() || device.type.trim().toLowerCase();
    const name = device.name.trim();
    const extensions = device.extensions;
    if (!component || !name) return null;
    if (component === 'cpu') {
        const id = toSearchIdString(device.id) ?? 'cpu';
        return buildCpuDeviceResult({ id, identifier: device.identifier, name, physicalCores: isFiniteNumber(extensions['physical_cores']) ? extensions['physical_cores'] : undefined, logicalCores: isFiniteNumber(extensions['logical_cores']) ? extensions['logical_cores'] : undefined, architecture: toTrimmedStringOrNull(extensions['architecture']) ?? undefined });
    }
    if (component === 'gpu') {
        const id = isFiniteNumber(device.id) && Number.isInteger(device.id) ? device.id : isFiniteNumber(extensions['gpu_index']) && Number.isInteger(extensions['gpu_index']) ? extensions['gpu_index'] : null;
        if (id === null) return null;
        return buildGpuDeviceResult({ id, gpuIndex: id, name, vendor: toTrimmedStringOrNull(extensions['vendor']) ?? undefined, type: device.type, memoryTotalMb: isFiniteNumber(extensions['memory_total_mb']) ? extensions['memory_total_mb'] : undefined });
    }
    if (component === 'disk' || component === 'volume') {
        const identifier = device.identifier ?? toTrimmedStringOrNull(extensions['mount']) ?? toTrimmedStringOrNull(extensions['filesystem']);
        if (!identifier) return null;
        return buildVolumeDeviceResult({ identifier, name, mount: toTrimmedStringOrNull(extensions['mount']) ?? undefined, filesystem: toTrimmedStringOrNull(extensions['filesystem']) ?? undefined, totalBytes: isFiniteNumber(extensions['total_bytes']) ? extensions['total_bytes'] : undefined, totalGb: isFiniteNumber(extensions['total_gb']) ? extensions['total_gb'] : undefined, percentUsed: isFiniteNumber(extensions['percent_used']) ? extensions['percent_used'] : undefined });
    }
    if (component === 'network') {
        const identifier = device.identifier ?? toSearchIdString(device.id);
        if (!identifier) return null;
        const addresses = isJsonArray(extensions['addresses']) ? extensions['addresses'].filter(isJsonObject).map((entry) => ({ address: toTrimmedStringOrNull(entry['address']) })) : [];
        return buildNetworkDeviceResult({ id: identifier, identifier, name, macAddress: toTrimmedStringOrNull(extensions['mac_address']) ?? undefined, addresses });
    }
    return null;
};

const normalizeRemoteResults = (payload: SearchResultsResponse | null): SearchItem[] => {
    if (!payload) return [];
    const plugins = payload.plugins
        .map((item: SearchResultPluginResponse): SearchItem => ({
            id: item.name,
            name: item.displayName,
            description: buildPluginSearchDescription(item.versionSoaiplugin, item.name),
            type: 'plugins',
            category: 'plugins',
            plugin: item.name,
            status: normalizeSearchStatus(item.state)
        }))
        .filter((entry) => Boolean(entry.id && entry.name));
    const models = payload.models
        .map((item: SearchResultModelResponse): SearchItem => ({
            id: item.universalId,
            name: item.displayName,
            description: buildModelSearchDescription(null, item.plugin),
            type: 'models',
            category: 'models',
            plugin: item.plugin,
            status: normalizeSearchStatus(item.state)
        }))
        .filter((entry) => Boolean(entry.id && entry.name));
    const devices = payload.devices.map((device) => normalizeRemoteDevice(device)).filter((entry): entry is SearchItem => entry !== null);
    const conversations = payload.conversations
        .map((item: SearchResultConversationResponse): SearchItem => ({
            id: item.id,
            name: item.title,
            description: buildConversationSearchDescription(item.lastModifiedAtMs),
            type: 'conversations',
            category: 'conversations',
            icon: item.isMessaging ? 'send' : 'chat',
            iconTone: item.isMessaging ? 'messaging' : undefined,
            accessibleContext: item.isMessaging ? i18n.t('chat.conversation.messaging') : undefined
        }))
        .filter((entry) => Boolean(entry.id && entry.name));
    const prompts = payload.prompts
        .map((item: SearchResultPromptResponse): SearchItem => ({
            id: item.id,
            name: item.name,
            description: buildPromptSearchDescription(item.modifiedAtMs),
            type: 'prompts',
            category: 'prompts',
            icon: 'prompt'
        }))
        .filter((entry) => Boolean(entry.id && entry.name));
    return [...plugins, ...models, ...devices, ...conversations, ...prompts];
};

const extractCollection = (value: JsonValue | null | undefined): (JsonValue | null)[] => {
    if (isJsonArray(value)) return Array.from(value);
    const record = isPlainObject(value) ? value : null;
    const nested = record ? (record['value'] ?? record['data'] ?? record['items']) : null;
    return isJsonArray(nested) ? Array.from(nested) : [];
};

export { extractCollection, normalizeModelForIndex, normalizePluginForIndex, normalizeRemoteResults };
