/* SoAI - Frontend model collection V1 boundary contract [frontend/assets/ts/core/models/modelRecordBoundary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { readOptionalBooleanValue, readOptionalFiniteNumberValue, readOptionalStringValue } from '@core/types/payloadValueReaders.ts';

const readOptionalObject = (value: JsonValue | undefined, label: string): JsonObject | undefined => {
    if (value === null || value === undefined) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object when provided`);
    return value;
};

const readOptionalArray = (value: JsonValue | undefined, label: string): JsonValue[] | undefined => {
    if (value === null || value === undefined) return undefined;
    if (!isJsonArray(value)) throw new TypeError(`${label} must be an array when provided`);
    return Array.from(value);
};

const decodeProviderMetadata = (value: JsonValue | undefined, label: string): JsonValue | undefined => {
    if (value === null || value === undefined) return undefined;
    if (typeof value === 'string') return value;
    if (!isJsonObject(value)) throw new TypeError(`${label} must be a string or object when provided`);
    const decoded: JsonObject = {};
    const id = readOptionalStringValue(value['id'], `${label}.id`);
    const name = readOptionalStringValue(value['name'], `${label}.name`);
    const apiUrl = readOptionalStringValue(value['api_url'], `${label}.api_url`);
    const status = readOptionalStringValue(value['status'], `${label}.status`);
    const lastError = readOptionalStringValue(value['last_error'], `${label}.last_error`);
    const lastCheckedAtMs = readOptionalFiniteNumberValue(value['last_checked_at_ms'], `${label}.last_checked_at_ms`);
    const contextWindowTokens = readOptionalFiniteNumberValue(value['context_window_tokens'], `${label}.context_window_tokens`);
    const createdAtMs = readOptionalFiniteNumberValue(value['created_at_ms'], `${label}.created_at_ms`);
    if (id !== undefined) decoded['id'] = id;
    if (name !== undefined) decoded['name'] = name;
    if (apiUrl !== undefined) decoded['apiUrl'] = apiUrl;
    if (status !== undefined) decoded['status'] = status;
    if (lastError !== undefined) decoded['lastError'] = lastError;
    if (lastCheckedAtMs !== undefined) decoded['lastCheckedAtMs'] = lastCheckedAtMs;
    if (contextWindowTokens !== undefined) decoded['contextWindowTokens'] = contextWindowTokens;
    if (createdAtMs !== undefined) decoded['createdAtMs'] = createdAtMs;
    return decoded;
};

const decodeVirtualModelConstituents = (value: JsonValue | undefined): JsonValue[] | undefined => {
    const entries = readOptionalArray(value, 'models.collection model.models');
    if (!entries) return undefined;
    return entries.map((entry, index) => {
        if (!isJsonObject(entry)) throw new TypeError(`models.collection model.models[${String(index)}] must be an object`);
        const universalId = readOptionalStringValue(entry['universal_id'], `models.collection model.models[${String(index)}].universal_id`);
        const parameters = readOptionalObject(entry['parameters'], `models.collection model.models[${String(index)}].parameters`);
        if (!universalId) throw new TypeError(`models.collection model.models[${String(index)}].universal_id must be a non-empty string`);
        return parameters === undefined ? { universalId } : { universalId, parameters };
    });
};

const decodeModelRecord = (record: JsonObject): ModelRecord => {
    const decoded: ModelRecord = {};
    const id = readOptionalStringValue(record['id'], 'models.collection model.id');
    const name = readOptionalStringValue(record['name'], 'models.collection model.name');
    const universalId = readOptionalStringValue(record['universal_id'], 'models.collection model.universal_id');
    const modelId = readOptionalStringValue(record['model_id'], 'models.collection model.model_id');
    const sourceModelId = readOptionalStringValue(record['source_model_id'], 'models.collection model.source_model_id');
    const rawUpstreamModelId = readOptionalStringValue(record['raw_upstream_model_id'], 'models.collection model.raw_upstream_model_id');
    const displayName = readOptionalStringValue(record['display_name'], 'models.collection model.display_name');
    const description = readOptionalStringValue(record['description'], 'models.collection model.description');
    const modelType = readOptionalStringValue(record['model_type'], 'models.collection model.model_type');
    const type = readOptionalStringValue(record['type'], 'models.collection model.type');
    const plugin = readOptionalStringValue(record['plugin'], 'models.collection model.plugin');
    const pluginStatus = readOptionalStringValue(record['plugin_status'], 'models.collection model.plugin_status');
    const status = readOptionalStringValue(record['status'], 'models.collection model.status');
    const statusMessage = readOptionalStringValue(record['status_message'], 'models.collection model.status_message');
    const modelRepository = readOptionalStringValue(record['model_repository'], 'models.collection model.model_repository');
    const path = readOptionalStringValue(record['path'], 'models.collection model.path');
    const family = readOptionalStringValue(record['family'], 'models.collection model.family');
    const license = readOptionalStringValue(record['license'], 'models.collection model.license');
    const quantization = readOptionalStringValue(record['quantization'], 'models.collection model.quantization');
    const providerId = readOptionalStringValue(record['provider_id'], 'models.collection model.provider_id');
    const strategy = readOptionalStringValue(record['strategy'], 'models.collection model.strategy');
    if (id !== undefined) decoded.id = id;
    if (name !== undefined) decoded.name = name;
    if (universalId !== undefined) decoded.universalId = universalId;
    if (modelId !== undefined) decoded.modelId = modelId;
    if (sourceModelId !== undefined) decoded.sourceModelId = sourceModelId;
    if (rawUpstreamModelId !== undefined) decoded.rawUpstreamModelId = rawUpstreamModelId;
    if (displayName !== undefined) decoded.displayName = displayName;
    if (description !== undefined) decoded.description = description;
    if (modelType !== undefined) decoded.modelType = modelType;
    if (type !== undefined) decoded.type = type;
    if (plugin !== undefined) decoded.plugin = plugin;
    if (pluginStatus !== undefined) decoded.pluginStatus = pluginStatus;
    if (status !== undefined) decoded.status = status;
    if (statusMessage !== undefined) decoded.statusMessage = statusMessage;
    if (modelRepository !== undefined) decoded.modelRepository = modelRepository;
    if (path !== undefined) decoded.path = path;
    if (family !== undefined) decoded.family = family;
    if (license !== undefined) decoded.license = license;
    if (quantization !== undefined) decoded.quantization = quantization;
    if (providerId !== undefined) decoded.providerId = providerId;
    if (strategy !== undefined) decoded.strategy = strategy;

    const hasAlias = readOptionalBooleanValue(record['has_alias'], 'models.collection model.has_alias');
    const isLoaded = readOptionalBooleanValue(record['is_loaded'], 'models.collection model.is_loaded');
    const isEnabled = readOptionalBooleanValue(record['is_enabled'], 'models.collection model.is_enabled');
    const isAvailable = readOptionalBooleanValue(record['is_available'], 'models.collection model.is_available');
    const isOrphaned = readOptionalBooleanValue(record['is_orphaned'], 'models.collection model.is_orphaned');
    const modelHasCustomParameters = readOptionalBooleanValue(record['model_has_custom_parameters'], 'models.collection model.model_has_custom_parameters');
    if (hasAlias !== undefined) decoded.hasAlias = hasAlias;
    if (isLoaded !== undefined) decoded.isLoaded = isLoaded;
    if (isEnabled !== undefined) decoded.isEnabled = isEnabled;
    if (isAvailable !== undefined) decoded.isAvailable = isAvailable;
    if (isOrphaned !== undefined) decoded.isOrphaned = isOrphaned;
    if (modelHasCustomParameters !== undefined) decoded.modelHasCustomParameters = modelHasCustomParameters;

    const parameterVersion = readOptionalFiniteNumberValue(record['parameter_version'], 'models.collection model.parameter_version');
    const createdAtMs = readOptionalFiniteNumberValue(record['created_at_ms'], 'models.collection model.created_at_ms');
    const lastModifiedAtMs = readOptionalFiniteNumberValue(record['last_modified_at_ms'], 'models.collection model.last_modified_at_ms');
    const lastDiscoveredAtMs = readOptionalFiniteNumberValue(record['last_discovered_at_ms'], 'models.collection model.last_discovered_at_ms');
    const lastUsedAtMs = readOptionalFiniteNumberValue(record['last_used_at_ms'], 'models.collection model.last_used_at_ms');
    const fileModifiedAtMs = readOptionalFiniteNumberValue(record['file_modified_at_ms'], 'models.collection model.file_modified_at_ms');
    const requestCount = readOptionalFiniteNumberValue(record['request_count'], 'models.collection model.request_count');
    const sizeBytes = readOptionalFiniteNumberValue(record['size_bytes'], 'models.collection model.size_bytes');
    const contextWindowTokens = readOptionalFiniteNumberValue(record['context_window_tokens'], 'models.collection model.context_window_tokens');
    if (parameterVersion !== undefined) decoded.parameterVersion = parameterVersion;
    if (createdAtMs !== undefined) decoded.createdAtMs = createdAtMs;
    if (lastModifiedAtMs !== undefined) decoded.lastModifiedAtMs = lastModifiedAtMs;
    if (lastDiscoveredAtMs !== undefined) decoded.lastDiscoveredAtMs = lastDiscoveredAtMs;
    if (lastUsedAtMs !== undefined) decoded.lastUsedAtMs = lastUsedAtMs;
    if (fileModifiedAtMs !== undefined) decoded.fileModifiedAtMs = fileModifiedAtMs;
    if (requestCount !== undefined) decoded.requestCount = requestCount;
    if (sizeBytes !== undefined) decoded.sizeBytes = sizeBytes;
    if (contextWindowTokens !== undefined) decoded.contextWindowTokens = contextWindowTokens;

    const provider = decodeProviderMetadata(record['provider'], 'models.collection model.provider');
    const providerMetadata = decodeProviderMetadata(record['provider_metadata'], 'models.collection model.provider_metadata');
    const capabilities = readOptionalArray(record['capabilities'], 'models.collection model.capabilities');
    const tags = readOptionalArray(record['tags'], 'models.collection model.tags');
    const modalities = readOptionalArray(record['modalities'], 'models.collection model.modalities');
    const openaiCapabilities = readOptionalObject(record['openai_capabilities'], 'models.collection model.openai_capabilities');
    const openaiCapabilitiesOverrides = readOptionalObject(record['openai_capabilities_overrides'], 'models.collection model.openai_capabilities_overrides');
    const models = decodeVirtualModelConstituents(record['models']);
    if (provider !== undefined) decoded.provider = provider;
    if (providerMetadata !== undefined) decoded.providerMetadata = providerMetadata;
    if (capabilities !== undefined) decoded.capabilities = capabilities;
    if (tags !== undefined) decoded.tags = tags;
    if (modalities !== undefined) decoded.modalities = modalities.filter((entry): entry is string => typeof entry === 'string');
    if (openaiCapabilities !== undefined) decoded.openaiCapabilities = openaiCapabilities;
    if (record['openai_capabilities_overrides'] === null) decoded.openaiCapabilitiesOverrides = null;
    else if (openaiCapabilitiesOverrides !== undefined) decoded.openaiCapabilitiesOverrides = openaiCapabilitiesOverrides;
    if (models !== undefined) decoded.models = models;
    return decoded;
};

export { decodeModelRecord };
