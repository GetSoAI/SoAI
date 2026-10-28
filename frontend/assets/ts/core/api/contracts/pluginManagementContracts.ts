/* SoAI - Frontend plugin management contracts [frontend/assets/ts/core/api/contracts/pluginManagementContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodePluginIncompatibility } from '@core/plugins/collectionSnapshot.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type BackendVariantAvailability = 'available' | 'hardware_warning' | 'unavailable';

interface BackendVariantCompatibility {
    status: 'compatible' | 'incompatible' | 'unknown';
    reasons: string[];
}

interface BackendVariantOptionResponse {
    compatibility?: BackendVariantCompatibility;
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

type InstalledBackendVariantResolution = 'resolved' | 'not_installed' | 'unavailable' | 'not_requested';

interface BackendVariantsResponse {
    installedVariantResolution?: InstalledBackendVariantResolution;
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
    installed?: boolean | null;
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
        ...(record['compatibility'] === undefined ? {} : { compatibility: decodeBackendVariantCompatibility(record['compatibility'], `${label}.compatibility`) }),
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

const decodeBackendVariantCompatibility = (value: JsonValue, label: string): BackendVariantCompatibility => {
    const record = requireRecord(value, label);
    const status = record['status'];
    if (status !== 'compatible' && status !== 'incompatible' && status !== 'unknown') throw new TypeError(`${label}.status is invalid.`);
    return { status, reasons: decodeStringArray(record['reasons'], `${label}.reasons`) };
};

const decodeInstalledBackendVariantResolution = (value: JsonValue): InstalledBackendVariantResolution => {
    if (value !== 'resolved' && value !== 'not_installed' && value !== 'unavailable' && value !== 'not_requested') throw new TypeError('Backend variants response.installed_variant_resolution is invalid.');
    return value;
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
        ...(record['installed_variant_resolution'] === undefined ? {} : { installedVariantResolution: decodeInstalledBackendVariantResolution(record['installed_variant_resolution']) }),
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
        state: readRequiredTrimmedString(record, 'state', `${label}.state`),
        incompatibility: decodePluginIncompatibility(incompatibility ?? null)
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

const decodePluginBackendUpdateResponse = (value: ApiResponsePayload): PluginBackendUpdateStatus => {
    const label = 'Plugin backend update response';
    const status = requireRecord(value, label);
    return {
        updateAvailable: readRequiredBooleanValue(status['update_available'], `${label}.update_available`),
        currentVersion: readNullableTrimmedStringValue(status['current_version'], `${label}.current_version`),
        latestVersion: readNullableTrimmedStringValue(status['latest_version'], `${label}.latest_version`),
        error: decodeUpdateError(status['error'], `${label}.error`),
        ...(status['installed'] === undefined ? {} : { installed: readRequiredBooleanValue(status['installed'], `${label}.installed`) })
    };
};

const decodePluginBackendUpdatesResponse = (value: ApiResponsePayload): PluginBackendUpdatesResponse => {
    const record = requireRecord(value, 'Plugin backend updates response');
    const response: PluginBackendUpdatesResponse = {};
    for (const [pluginName, entry] of Object.entries(record)) {
        response[pluginName] = decodePluginBackendUpdateResponse(entry);
    }
    return response;
};

const serializeBackendVariantSelectionRequest = (variantId: string): JsonObject => ({ 'backend_variant_id': variantId });

export { decodeBackendVariantsResponse, decodePluginBackendUpdateResponse, decodePluginBackendUpdatesResponse, decodePluginCompatibilityOverrideResponse, serializeBackendVariantSelectionRequest };
export type { BackendVariantOptionResponse, BackendVariantsResponse, PluginBackendUpdateError, PluginBackendUpdatesResponse, PluginBackendUpdateStatus, PluginCompatibilityOverrideResponse };
