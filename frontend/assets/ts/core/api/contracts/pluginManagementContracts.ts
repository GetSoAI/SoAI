/* SoAI - Frontend plugin management contracts [frontend/assets/ts/core/api/contracts/pluginManagementContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type BackendVariantAvailability = 'available' | 'hardware_warning' | 'unavailable';

interface BackendVariantOptionResponse {
    id: string;
    label: string;
    description: string | null;
    available: boolean;
    selectable: boolean;
    availabilityType: BackendVariantAvailability;
    unavailableReason: string | null;
    platformLabel: string | null;
    supportedOs: string[];
    supportedArch: string[];
    supportedPlatforms: string[];
    gpuBindingRuntimeFamily: string | null;
}

interface BackendVariantsResponse {
    selectedVariantId: string;
    installedVariantId: string | null;
    options: BackendVariantOptionResponse[];
    availableCount: number;
}

interface PluginCompatibilityOverrideResponse {
    plugin: string;
    state: string;
    incompatibility: JsonObject | null;
}

interface PluginBackendUpdateError {
    code: string;
    message: string;
    details: JsonObject | null;
}

interface PluginBackendUpdateStatus {
    updateAvailable: boolean;
    currentVersion: string | null;
    latestVersion: string | null;
    error: PluginBackendUpdateError | null;
}

type PluginBackendUpdatesResponse = Record<string, PluginBackendUpdateStatus>;

const decodeStringArray = (value: JsonValue | undefined, label: string): string[] => {
    if (value === undefined) return [];
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => readRequiredTrimmedString({ entry }, 'entry', `${label}[${String(index)}]`));
};

const decodeAvailability = (value: JsonValue | undefined, label: string): BackendVariantAvailability => {
    if (value !== 'available' && value !== 'hardware_warning' && value !== 'unavailable') {
        throw new TypeError(`${label} is invalid.`);
    }
    return value;
};

const decodeBackendVariantOption = (value: JsonValue, index: number): BackendVariantOptionResponse => {
    const label = `Backend variants response.options[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        label: readRequiredTrimmedString(record, 'label', `${label}.label`),
        description: readNullableTrimmedStringValue(record['description'], `${label}.description`),
        available: readRequiredBooleanValue(record['available'], `${label}.available`),
        selectable: readRequiredBooleanValue(record['selectable'], `${label}.selectable`),
        availabilityType: decodeAvailability(record['availability_type'], `${label}.availability_type`),
        unavailableReason: readNullableTrimmedStringValue(record['unavailable_reason'], `${label}.unavailable_reason`),
        platformLabel: readNullableTrimmedStringValue(record['platform_label'], `${label}.platform_label`),
        supportedOs: decodeStringArray(record['supported_os'], `${label}.supported_os`),
        supportedArch: decodeStringArray(record['supported_arch'], `${label}.supported_arch`),
        supportedPlatforms: decodeStringArray(record['supported_platforms'], `${label}.supported_platforms`),
        gpuBindingRuntimeFamily: readNullableTrimmedStringValue(record['gpu_binding_runtime_family'], `${label}.gpu_binding_runtime_family`)
    };
};

const decodeBackendVariantsResponse = (value: ApiResponsePayload): BackendVariantsResponse => {
    const label = 'Backend variants response';
    const record = requireRecord(value, label);
    const options = record['options'];
    if (!Array.isArray(options)) throw new TypeError(`${label}.options must be an array.`);
    const decodedOptions = options.map(decodeBackendVariantOption);
    const selected = readRequiredTrimmedString(record, 'selected_variant_id', `${label}.selected_variant_id`);
    if (!decodedOptions.some((option) => option.id === selected)) throw new TypeError(`${label}.selected_variant_id must identify an option.`);
    return {
        selectedVariantId: selected,
        installedVariantId: readNullableTrimmedStringValue(record['installed_variant_id'], `${label}.installed_variant_id`),
        options: decodedOptions,
        availableCount: readRequiredNonNegativeIntegerValue(record['available_count'], `${label}.available_count`)
    };
};

const decodePluginCompatibilityOverrideResponse = (value: ApiResponsePayload): PluginCompatibilityOverrideResponse => {
    const label = 'Plugin compatibility override response';
    const record = requireRecord(value, label);
    const incompatibility = record['incompatibility'];
    return {
        plugin: readRequiredTrimmedString(record, 'plugin', `${label}.plugin`),
        state: typeof record['state'] === 'string' ? record['state'].trim() : '',
        incompatibility: incompatibility === null || incompatibility === undefined ? null : requireRecord(incompatibility, `${label}.incompatibility`)
    };
};

const decodeUpdateError = (value: JsonValue | undefined, label: string): PluginBackendUpdateError | null => {
    if (value === null || value === undefined) return null;
    const record = requireRecord(value, label);
    return {
        code: readRequiredTrimmedString(record, 'code', `${label}.code`),
        message: readRequiredTrimmedString(record, 'message', `${label}.message`),
        details: record['details'] === null || record['details'] === undefined ? null : requireRecord(record['details'], `${label}.details`)
    };
};

const decodePluginBackendUpdatesResponse = (value: ApiResponsePayload): PluginBackendUpdatesResponse => {
    const record = requireRecord(value, 'Plugin backend updates response');
    const response: PluginBackendUpdatesResponse = {};
    for (const [pluginName, entry] of Object.entries(record)) {
        const label = `Plugin backend updates response.${pluginName}`;
        const status = requireRecord(entry, label);
        response[pluginName] = {
            updateAvailable: readRequiredBooleanValue(status['update_available'], `${label}.update_available`),
            currentVersion: readNullableTrimmedStringValue(status['current_version'], `${label}.current_version`),
            latestVersion: readNullableTrimmedStringValue(status['latest_version'], `${label}.latest_version`),
            error: decodeUpdateError(status['error'], `${label}.error`)
        };
    }
    return response;
};

const serializeBackendVariantSelectionRequest = (variantId: string): JsonObject => ({ 'backend_variant_id': variantId });

export { decodeBackendVariantsResponse, decodePluginBackendUpdatesResponse, decodePluginCompatibilityOverrideResponse, serializeBackendVariantSelectionRequest };
export type { BackendVariantOptionResponse, BackendVariantsResponse, PluginBackendUpdateError, PluginBackendUpdatesResponse, PluginBackendUpdateStatus, PluginCompatibilityOverrideResponse };
