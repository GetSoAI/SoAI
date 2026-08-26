/* SoAI - Model catalog response validation and decoding [frontend/assets/ts/core/api/contracts/modelCatalogContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { LocalModelCatalogEntry, ModelCatalogEntry, ModelCatalogProvider, ModelCatalogResponse, VirtualModelCatalogConstituent, VirtualModelCatalogEntry } from '@core/api/contracts/modelCatalogContractTypes.ts';
import { readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const decodeJsonArray = (value: JsonValue | undefined, label: string): JsonValue[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return [...value];
};

const decodeStringArray = (value: JsonValue | undefined, label: string): string[] => {
    return decodeJsonArray(value, label).map((entry, index) => readRequiredTrimmedString({ entry }, 'entry', `${label}[${String(index)}]`));
};

const decodeNullableRecord = (value: JsonValue | undefined, label: string): JsonObject | null => {
    if (value === null || value === undefined) return null;
    return requireRecord(value, label);
};

const decodeNullablePositiveInteger = (value: JsonValue | undefined, label: string): number | null => {
    if (value === null || value === undefined) return null;
    return readRequiredPositiveIntegerValue(value, label);
};

const decodeProvider = (value: JsonValue | undefined, label: string): ModelCatalogProvider | null => {
    if (value === null || value === undefined) return null;
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readNullableTrimmedStringValue(record['name'], `${label}.name`),
        apiUrl: readNullableTrimmedStringValue(record['api_url'], `${label}.api_url`),
        status: readNullableTrimmedStringValue(record['status'], `${label}.status`),
        lastError: readNullableTrimmedStringValue(record['last_error'], `${label}.last_error`),
        lastCheckedAtMs: readNullableNonNegativeIntegerValue(record['last_checked_at_ms'], `${label}.last_checked_at_ms`),
        contextWindowTokens: decodeNullablePositiveInteger(record['context_window_tokens'], `${label}.context_window_tokens`),
        createdAtMs: readNullableNonNegativeIntegerValue(record['created_at_ms'], `${label}.created_at_ms`)
    };
};

const decodeLocalModel = (value: JsonValue, label: string): LocalModelCatalogEntry => {
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        plugin: readRequiredTrimmedString(record, 'plugin', `${label}.plugin`),
        modelId: readRequiredTrimmedString(record, 'model_id', `${label}.model_id`),
        universalId: readRequiredTrimmedString(record, 'universal_id', `${label}.universal_id`),
        type: readRequiredTrimmedString(record, 'type', `${label}.type`),
        hasAlias: readRequiredBooleanValue(record['has_alias'], `${label}.has_alias`),
        modelRepository: readNullableTrimmedStringValue(record['model_repository'], `${label}.model_repository`),
        description: readNullableTrimmedStringValue(record['description'], `${label}.description`),
        isLoaded: readRequiredBooleanValue(record['is_loaded'], `${label}.is_loaded`),
        pluginStatus: readRequiredTrimmedString(record, 'plugin_status', `${label}.plugin_status`),
        status: readRequiredTrimmedString(record, 'status', `${label}.status`),
        isEnabled: readRequiredBooleanValue(record['is_enabled'], `${label}.is_enabled`),
        isAvailable: readRequiredBooleanValue(record['is_available'], `${label}.is_available`),
        modelHasCustomParameters: readRequiredBooleanValue(record['model_has_custom_parameters'], `${label}.model_has_custom_parameters`),
        parameterVersion: readRequiredNonNegativeIntegerValue(record['parameter_version'], `${label}.parameter_version`),
        isOrphaned: readRequiredBooleanValue(record['is_orphaned'], `${label}.is_orphaned`),
        statusMessage: readRequiredStringValue(record['status_message'], `${label}.status_message`),
        createdAtMs: readNullableNonNegativeIntegerValue(record['created_at_ms'], `${label}.created_at_ms`),
        lastModifiedAtMs: readNullableNonNegativeIntegerValue(record['last_modified_at_ms'], `${label}.last_modified_at_ms`),
        lastDiscoveredAtMs: readNullableNonNegativeIntegerValue(record['last_discovered_at_ms'], `${label}.last_discovered_at_ms`),
        lastUsedAtMs: readNullableNonNegativeIntegerValue(record['last_used_at_ms'], `${label}.last_used_at_ms`),
        fileModifiedAtMs: readNullableNonNegativeIntegerValue(record['file_modified_at_ms'], `${label}.file_modified_at_ms`),
        requestCount: readRequiredNonNegativeIntegerValue(record['request_count'], `${label}.request_count`),
        sizeBytes: readNullableNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`),
        path: readNullableTrimmedStringValue(record['path'], `${label}.path`),
        family: readNullableTrimmedStringValue(record['family'], `${label}.family`),
        license: readNullableTrimmedStringValue(record['license'], `${label}.license`),
        quantization: readNullableTrimmedStringValue(record['quantization'], `${label}.quantization`),
        capabilities: decodeJsonArray(record['capabilities'], `${label}.capabilities`),
        tags: decodeJsonArray(record['tags'], `${label}.tags`),
        provider: decodeProvider(record['provider'], `${label}.provider`),
        providerId: readNullableTrimmedStringValue(record['provider_id'], `${label}.provider_id`),
        providerMetadata: decodeProvider(record['provider_metadata'], `${label}.provider_metadata`),
        sourceModelId: readRequiredTrimmedString(record, 'source_model_id', `${label}.source_model_id`),
        rawUpstreamModelId: readNullableTrimmedStringValue(record['raw_upstream_model_id'], `${label}.raw_upstream_model_id`),
        openaiCapabilitiesOverrides: decodeNullableRecord(record['openai_capabilities_overrides'], `${label}.openai_capabilities_overrides`),
        modalities: record['modalities'] === undefined ? [] : decodeStringArray(record['modalities'], `${label}.modalities`),
        openaiCapabilities: decodeNullableRecord(record['openai_capabilities'], `${label}.openai_capabilities`),
        modelType: readNullableTrimmedStringValue(record['model_type'], `${label}.model_type`),
        contextWindowTokens: decodeNullablePositiveInteger(record['context_window_tokens'], `${label}.context_window_tokens`)
    };
};

const decodeVirtualConstituent = (value: JsonValue, label: string): VirtualModelCatalogConstituent => {
    const record = requireRecord(value, label);
    return {
        universalId: readRequiredTrimmedString(record, 'universal_id', `${label}.universal_id`),
        parameters: requireRecord(record['parameters'], `${label}.parameters`)
    };
};

const decodeVirtualModel = (value: JsonValue, label: string): VirtualModelCatalogEntry => {
    const record = requireRecord(value, label);
    const models = record['models'];
    if (!Array.isArray(models)) throw new TypeError(`${label}.models must be an array.`);
    const type = readRequiredEnumValue(record['type'], `${label}.type`, ['virtual']);
    const modelType = readRequiredEnumValue(record['model_type'], `${label}.model_type`, ['virtual']);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        type,
        modelType,
        strategy: readRequiredEnumValue(record['strategy'], `${label}.strategy`, ['load_balancing', 'failover']),
        models: models.map((entry, index) => decodeVirtualConstituent(entry, `${label}.models[${String(index)}]`)),
        isEnabled: readRequiredBooleanValue(record['is_enabled'], `${label}.is_enabled`),
        modalities: record['modalities'] === undefined ? [] : decodeStringArray(record['modalities'], `${label}.modalities`),
        openaiCapabilities: decodeNullableRecord(record['openai_capabilities'], `${label}.openai_capabilities`),
        contextWindowTokens: decodeNullablePositiveInteger(record['context_window_tokens'], `${label}.context_window_tokens`)
    };
};

const isLocalModelCatalogEntry = (entry: ModelCatalogEntry): entry is LocalModelCatalogEntry => 'universalId' in entry;

const decodeModelCatalogResponse = (value: ApiResponsePayload): ModelCatalogResponse => {
    const record = requireRecord(value, 'Model catalog response');
    const response: ModelCatalogResponse = {};
    for (const [groupName, groupValue] of Object.entries(record)) {
        if (!Array.isArray(groupValue)) throw new TypeError(`Model catalog response.${groupName} must be an array.`);
        response[groupName] = groupValue.map((entry, index): ModelCatalogEntry => {
            const label = `Model catalog response.${groupName}[${String(index)}]`;
            return groupName === 'virtual' ? decodeVirtualModel(entry, label) : decodeLocalModel(entry, label);
        });
    }
    return response;
};

export { decodeModelCatalogResponse, isLocalModelCatalogEntry };
export type { LocalModelCatalogEntry, ModelCatalogEntry, ModelCatalogProvider, ModelCatalogResponse, VirtualModelCatalogConstituent, VirtualModelCatalogEntry } from '@core/api/contracts/modelCatalogContractTypes.ts';
