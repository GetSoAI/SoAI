/* SoAI - Shared plugins collection snapshot [frontend/assets/ts/core/plugins/collectionSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isPluginRecord } from '@core/types/pluginRecordGuards.ts';
import { parsePluginModelRepository } from '@core/plugins/modelRepositoryContract.ts';
import type { PluginIncompatibilityContext } from '@core/types/catalogPluginTypes.ts';

type PluginCollectionEntry = JsonObject;

const requirePluginStringField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    if (!isString(entry[key])) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be a string`);
    }
};

const requirePluginNonEmptyStringField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    const value = entry[key];
    if (!isString(value) || !value.trim()) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be a non-empty string`);
    }
};

const requirePluginNullableStringField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    const value = entry[key];
    if (value !== null && !isString(value)) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be a string or null`);
    }
};

const requirePluginBooleanField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    if (!isBoolean(entry[key])) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be a boolean`);
    }
};

const requirePluginObjectField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    if (!isJsonObject(entry[key])) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be an object`);
    }
};

const requirePluginNullableObjectField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    const value = entry[key];
    if (value !== null && !isJsonObject(value)) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be an object or null`);
    }
};

const requirePluginStringArrayField = (entry: PluginCollectionEntry, key: string, index: number): void => {
    const value = entry[key];
    if (!isJsonArray(value)) {
        throw new TypeError(`plugins.collection entry ${index} field "${key}" must be an array`);
    }
    value.forEach((item, itemIndex) => {
        if (!isString(item) || !item.trim()) {
            throw new TypeError(`plugins.collection entry ${index} field "${key}" item ${itemIndex} must be a non-empty string`);
        }
    });
};

const validatePluginDependencies = (entry: PluginCollectionEntry, index: number): void => {
    const dependencies = entry['dependencies'];
    if (!isJsonObject(dependencies)) {
        throw new TypeError(`plugins.collection entry ${index} field "dependencies" must be an object`);
    }
    const plugins = dependencies['plugins'];
    const packages = dependencies['packages'];
    if (!isJsonArray(plugins) || !plugins.every((item) => isString(item) && item.trim())) {
        throw new TypeError(`plugins.collection entry ${index} dependencies.plugins must be a string array`);
    }
    if (!isJsonArray(packages) || !packages.every((item) => isString(item) && item.trim())) {
        throw new TypeError(`plugins.collection entry ${index} dependencies.packages must be a string array`);
    }
};

const validatePluginCircuitBreaker = (entry: PluginCollectionEntry, index: number): void => {
    const circuitBreaker = entry['circuit_breaker'];
    if (!isJsonObject(circuitBreaker)) {
        throw new TypeError(`plugins.collection entry ${index} field "circuit_breaker" must be an object`);
    }
    if (!isString(circuitBreaker['state']) || !circuitBreaker['state'].trim()) {
        throw new TypeError(`plugins.collection entry ${index} circuit_breaker.state must be a non-empty string`);
    }
    if (!isBoolean(circuitBreaker['is_open'])) {
        throw new TypeError(`plugins.collection entry ${index} circuit_breaker.is_open must be a boolean`);
    }
    if (!isFiniteNumber(circuitBreaker['failure_count'])) {
        throw new TypeError(`plugins.collection entry ${index} circuit_breaker.failure_count must be a number`);
    }
    if (!isFiniteNumber(circuitBreaker['last_failure_at_ms'])) {
        throw new TypeError(`plugins.collection entry ${index} circuit_breaker.last_failure_at_ms must be a number`);
    }
};

const validatePluginStats = (entry: PluginCollectionEntry, index: number): void => {
    const stats = entry['stats'];
    if (!isJsonObject(stats)) {
        throw new TypeError(`plugins.collection entry ${index} field "stats" must be an object`);
    }
    if (!isFiniteNumber(stats['model_count'])) {
        throw new TypeError(`plugins.collection entry ${index} stats.model_count must be a number`);
    }
    if (!isFiniteNumber(stats['provider_count'])) {
        throw new TypeError(`plugins.collection entry ${index} stats.provider_count must be a number`);
    }
};

const validatePluginCollectionEntry = (entry: PluginCollectionEntry, index: number): void => {
    requirePluginNonEmptyStringField(entry, 'name', index);
    requirePluginNonEmptyStringField(entry, 'display_name', index);
    requirePluginStringField(entry, 'description_soaiplugin', index);
    requirePluginStringField(entry, 'author_soaiplugin', index);
    requirePluginNonEmptyStringField(entry, 'version_soaiplugin', index);
    requirePluginNonEmptyStringField(entry, 'license_soaiplugin', index);
    requirePluginStringField(entry, 'website_soaiplugin', index);
    requirePluginNullableStringField(entry, 'license_managed_backend', index);
    requirePluginNonEmptyStringField(entry, 'core_compat', index);
    requirePluginNonEmptyStringField(entry, 'state', index);
    requirePluginStringArrayField(entry, 'model_types', index);
    requirePluginStringArrayField(entry, 'aliases', index);
    requirePluginStringArrayField(entry, 'modalities', index);
    requirePluginBooleanField(entry, 'installed', index);
    requirePluginBooleanField(entry, 'is_builtin', index);
    requirePluginBooleanField(entry, 'is_persistent', index);
    requirePluginBooleanField(entry, 'is_enabled', index);
    requirePluginBooleanField(entry, 'is_available', index);
    requirePluginBooleanField(entry, 'permanently_disabled', index);
    requirePluginBooleanField(entry, 'user_enabled_once', index);
    requirePluginObjectField(entry, 'external_provider_defaults', index);
    requirePluginNullableObjectField(entry, 'incompatibility', index);
    requirePluginObjectField(entry, 'capabilities', index);
    requirePluginObjectField(entry, 'technical', index);
    requirePluginNullableStringField(entry, 'logo_revision', index);
    validatePluginDependencies(entry, index);
    validatePluginStats(entry, index);
    validatePluginCircuitBreaker(entry, index);
};

const decodeIncompatibilityStringArray = (details: JsonObject, key: string, label: string): string[] | undefined => {
    const value = details[key];
    if (value === undefined) return undefined;
    if (!isJsonArray(value) || !value.every(isString)) throw new TypeError(`${label} must be a string array`);
    return [...value];
};

const decodePluginIncompatibility = (value: JsonValue): JsonObject | null => {
    if (value === null) return null;
    if (!isJsonObject(value)) throw new TypeError('plugins.collection incompatibility must be an object or null');
    const decoded: JsonObject = {};
    if (value['reason'] !== undefined) decoded['reason'] = value['reason'];
    if (value['can_override'] !== undefined) decoded['canOverride'] = value['can_override'];
    if (value['is_overridden'] !== undefined) decoded['isOverridden'] = value['is_overridden'];
    if (value['message'] !== undefined) decoded['message'] = value['message'];
    if (value['details'] !== undefined) {
        if (!isJsonObject(value['details'])) throw new TypeError('plugins.collection incompatibility.details must be an object');
        const details = value['details'];
        const context: PluginIncompatibilityContext = {};
        if (details['required_version'] !== undefined) context.requiredVersion = String(details['required_version']);
        if (details['detected_version'] !== undefined) context.detectedVersion = String(details['detected_version']);
        const detectedOs = details['detected_os'] !== undefined ? details['detected_os'] : details['detected_platform'];
        if (detectedOs !== undefined) context.detectedOs = detectedOs === null ? null : String(detectedOs);
        const requiredOsKey = details['required_os'] !== undefined ? 'required_os' : 'required_platforms';
        const requiredOs = decodeIncompatibilityStringArray(details, requiredOsKey, 'plugins.collection incompatibility OS requirements');
        if (requiredOs !== undefined) {
            context.requiredOs = requiredOs;
        }
        const requiredGpu = decodeIncompatibilityStringArray(details, 'required_gpu', 'plugins.collection incompatibility.details.required_gpu');
        if (requiredGpu !== undefined) context.requiredGpu = requiredGpu;
        const detectedVendors = decodeIncompatibilityStringArray(details, 'detected_vendors', 'plugins.collection incompatibility.details.detected_vendors');
        if (detectedVendors !== undefined) context.detectedVendors = detectedVendors;
        const missingDependencies = decodeIncompatibilityStringArray(details, 'missing_dependencies', 'plugins.collection incompatibility.details.missing_dependencies');
        if (missingDependencies !== undefined) context.missingDependencies = missingDependencies;
        const declaredDependencies = decodeIncompatibilityStringArray(details, 'declared_dependencies', 'plugins.collection incompatibility.details.declared_dependencies');
        if (declaredDependencies !== undefined) context.declaredDependencies = declaredDependencies;
        decoded['details'] = context;
    }
    return decoded;
};

const decodePluginCapabilities = (value: JsonValue): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError('plugins.collection capabilities must be an object');
    const decoded: JsonObject = {};
    if (value['has_configuration'] !== undefined) decoded['hasConfiguration'] = value['has_configuration'];
    if (value['supports_backend_installation'] !== undefined) decoded['supportsBackendInstallation'] = value['supports_backend_installation'];
    if (value['supports_model_deletion'] !== undefined) decoded['supportsModelDeletion'] = value['supports_model_deletion'];
    if (value['supports_model_download'] !== undefined) decoded['supportsModelDownload'] = value['supports_model_download'];
    if (value['supports_external_providers'] !== undefined) decoded['supportsExternalProviders'] = value['supports_external_providers'];
    if (value['supports_gpu_binding'] !== undefined) decoded['supportsGpuBinding'] = value['supports_gpu_binding'];
    if (value['local_resources'] !== undefined) decoded['localResources'] = value['local_resources'];
    if (value['local_models'] !== undefined) decoded['localModels'] = value['local_models'];
    if (value['supports_cloning'] !== undefined) decoded['supportsCloning'] = value['supports_cloning'];
    if (value['openai'] !== undefined) decoded['openai'] = value['openai'];
    if (value['external_provider_mode'] !== undefined) decoded['externalProviderMode'] = value['external_provider_mode'];
    return decoded;
};

const decodePluginStats = (value: JsonValue): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError('plugins.collection stats must be an object');
    const decoded: JsonObject = {
        modelCount: value['model_count'] ?? 0,
        providerCount: value['provider_count'] ?? 0
    };
    if (value['backend_variant_available_count'] !== undefined) decoded['backendVariantAvailableCount'] = value['backend_variant_available_count'];
    return decoded;
};

const decodePluginTechnical = (value: JsonValue): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError('plugins.collection technical must be an object');
    const decoded: JsonObject = {};
    if (value['max_concurrent_requests'] !== undefined) decoded['maxConcurrentRequests'] = value['max_concurrent_requests'];
    if (value['file_path'] !== undefined) decoded['filePath'] = value['file_path'];
    if (value['file_hash'] !== undefined) decoded['fileHash'] = value['file_hash'];
    if (value['first_seen_at_ms'] !== undefined) decoded['firstSeenAtMs'] = value['first_seen_at_ms'];
    if (value['last_seen_at_ms'] !== undefined) decoded['lastSeenAtMs'] = value['last_seen_at_ms'];
    if (value['instance_loaded'] !== undefined) decoded['instanceLoaded'] = value['instance_loaded'];
    if (value['status'] !== undefined) decoded['status'] = value['status'];
    return decoded;
};

const decodePluginCircuitBreaker = (value: JsonValue): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError('plugins.collection circuit_breaker must be an object');
    const decoded: JsonObject = {
        state: value['state'] ?? '',
        isOpen: value['is_open'] ?? false,
        failureCount: value['failure_count'] ?? 0,
        lastFailureAtMs: value['last_failure_at_ms'] ?? 0
    };
    if (value['recovery_timeout_sec'] !== undefined) decoded['recoveryTimeoutSec'] = value['recovery_timeout_sec'];
    if (value['failure_window_sec'] !== undefined) decoded['failureWindowSec'] = value['failure_window_sec'];
    if (value['failure_threshold'] !== undefined) decoded['failureThreshold'] = value['failure_threshold'];
    if (value['was_enabled'] !== undefined) decoded['wasEnabled'] = value['was_enabled'];
    return decoded;
};

const decodePluginCollectionEntry = (entry: PluginCollectionEntry): PluginCollectionEntry => {
    const decoded: PluginCollectionEntry = {
        name: entry['name'] ?? '',
        displayName: entry['display_name'] ?? '',
        descriptionSoaiplugin: entry['description_soaiplugin'] ?? '',
        authorSoaiplugin: entry['author_soaiplugin'] ?? '',
        versionSoaiplugin: entry['version_soaiplugin'] ?? '',
        licenseSoaiplugin: entry['license_soaiplugin'] ?? '',
        websiteSoaiplugin: entry['website_soaiplugin'] ?? '',
        modelTypes: entry['model_types'] ?? [],
        externalProviderDefaults: entry['external_provider_defaults'] ?? {},
        coreCompat: entry['core_compat'] ?? '',
        aliases: entry['aliases'] ?? [],
        dependencies: entry['dependencies'] ?? {},
        modalities: entry['modalities'] ?? [],
        state: entry['state'] ?? '',
        installed: entry['installed'] ?? false,
        isBuiltin: entry['is_builtin'] ?? false,
        isPersistent: entry['is_persistent'] ?? false,
        isEnabled: entry['is_enabled'] ?? false,
        isAvailable: entry['is_available'] ?? false,
        permanentlyDisabled: entry['permanently_disabled'] ?? false,
        incompatibility: decodePluginIncompatibility(entry['incompatibility'] ?? null),
        capabilities: decodePluginCapabilities(entry['capabilities'] ?? {}),
        stats: decodePluginStats(entry['stats'] ?? {}),
        technical: decodePluginTechnical(entry['technical'] ?? {}),
        circuitBreaker: decodePluginCircuitBreaker(entry['circuit_breaker'] ?? {}),
        userEnabledOnce: entry['user_enabled_once'] ?? false
    };
    if (entry['license_managed_backend'] !== undefined) decoded['licenseManagedBackend'] = entry['license_managed_backend'];
    if (entry['website_backend'] !== undefined) decoded['websiteBackend'] = entry['website_backend'];
    if (entry['model_repository'] !== undefined) decoded['modelRepository'] = parsePluginModelRepository(entry['model_repository']);
    decoded['logoRevision'] = entry['logo_revision'] ?? null;
    return decoded;
};

const parsePluginsCollectionSnapshot = <T>(payload: T): PluginCollectionEntry[] => {
    if (!isJsonArray(payload)) {
        throw new TypeError('plugins.collection snapshot payload must be an array');
    }
    const entries: PluginCollectionEntry[] = [];
    payload.forEach((entry, index) => {
        if (!isJsonObject(entry)) {
            throw new TypeError(`plugins.collection entry ${index} must be an object`);
        }
        validatePluginCollectionEntry(entry, index);
        entries.push(decodePluginCollectionEntry(entry));
    });
    return entries;
};

const parsePluginsCollectionState = <T>(payload: T): PluginCollectionEntry[] => {
    if (!isJsonArray(payload)) throw new TypeError('plugins.collection state must be an array');
    return payload.map((entry, index) => {
        if (!isJsonObject(entry) || !isPluginRecord(entry) || !isString(entry['displayName']) || !entry['displayName'].trim()) {
            throw new TypeError(`plugins.collection state entry ${index} is invalid`);
        }
        return entry;
    });
};

export { decodePluginIncompatibility, parsePluginsCollectionSnapshot, parsePluginsCollectionState };
export type { JsonValue, PluginCollectionEntry };
