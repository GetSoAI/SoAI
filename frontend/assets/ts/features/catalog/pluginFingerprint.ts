/* SoAI - Catalog feature plugin fingerprint [frontend/assets/ts/features/catalog/pluginFingerprint.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { isNumber } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const stablePluginFingerprint = (candidate: JsonValue): string => {
    if (!isJsonObject(candidate)) return '';
    const stats = isJsonObject(candidate['stats']) ? candidate['stats'] : null;
    const capabilities = isJsonObject(candidate['capabilities']) ? candidate['capabilities'] : null;
    const incompatibility = isJsonObject(candidate['incompatibility']) ? candidate['incompatibility'] : null;
    const circuitBreaker = isJsonObject(candidate['circuitBreaker']) ? candidate['circuitBreaker'] : null;
    const compatibility = isJsonObject(candidate['compatibility']) ? candidate['compatibility'] : null;
    const providerDefaults = isJsonObject(candidate['externalProviderDefaults']) ? candidate['externalProviderDefaults'] : null;
    const technical = isJsonObject(candidate['technical']) ? candidate['technical'] : null;
    const modelTypes = isJsonArray(candidate['modelTypes']) ? candidate['modelTypes'].map((value) => String(value)) : [];
    return stableJsonStringify({
        id: toTrimmedString(candidate['id']),
        name: toTrimmedString(candidate['name']),
        displayName: toTrimmedString(candidate['displayName']),
        descriptionSoaiplugin: toTrimmedString(candidate['descriptionSoaiplugin']),
        authorSoaiplugin: toTrimmedString(candidate['authorSoaiplugin']),
        versionSoaiplugin: toTrimmedString(candidate['versionSoaiplugin']),
        state: toTrimmedString(candidate['state']),
        isEnabled: candidate['isEnabled'] === true,
        isAvailable: candidate['isAvailable'] === true,
        isPersistent: candidate['isPersistent'] === true,
        isBuiltin: candidate['isBuiltin'] === true,
        permanentlyDisabled: candidate['permanentlyDisabled'] === true,
        disabledReason: toTrimmedString(candidate['disabledReason']),
        fileStatus: toTrimmedString(candidate['fileStatus']),
        backendVersion: toTrimmedString(candidate['backendVersion']),
        externalProviderDefaults: providerDefaults,
        modelTypes: modelTypes,
        modelCount: isNumber(stats?.['modelCount']) ? stats['modelCount'] : null,
        providerCount: isNumber(stats?.['providerCount']) ? stats['providerCount'] : null,
        backendVariantAvailableCount: isNumber(stats?.['backendVariantAvailableCount']) ? stats['backendVariantAvailableCount'] : null,
        capabilityHasConfiguration: capabilities?.['hasConfiguration'] === true,
        capabilitySupportsCloning: capabilities?.['supportsCloning'] === true,
        capabilitySupportsBackendInstallation: capabilities?.['supportsBackendInstallation'] === true,
        capabilitySupportsModelDeletion: capabilities?.['supportsModelDeletion'] === true,
        capabilitySupportsModelDownload: capabilities?.['supportsModelDownload'] === true,
        capabilityExternalProviderMode: toTrimmedString(capabilities?.['externalProviderMode']),
        capabilityOpenAi: capabilities?.['openai'] ?? null,
        incompatibilityReason: toTrimmedString(incompatibility?.['reason']),
        incompatibilityCanOverride: incompatibility?.['canOverride'] === true,
        incompatibilityIsOverridden: incompatibility?.['isOverridden'] === true,
        incompatibilityMessage: toTrimmedString(incompatibility?.['message']),
        incompatibilityDetails: incompatibility?.['details'] ?? null,
        compatibilityReason: toTrimmedString(compatibility?.['reason']),
        compatibilityCanOverride: compatibility?.['canOverride'] === true,
        compatibilityIsOverridden: compatibility?.['isOverridden'] === true,
        compatibilityMessage: toTrimmedString(compatibility?.['message']),
        compatibilityDetails: compatibility?.['details'] ?? null,
        breakerState: toTrimmedString(circuitBreaker?.['state']),
        breakerOpen: circuitBreaker?.['isOpen'] === true,
        breakerFailureCount: isNumber(circuitBreaker?.['failureCount']) ? circuitBreaker['failureCount'] : null,
        breakerFailureThreshold: isNumber(circuitBreaker?.['failureThreshold']) ? circuitBreaker['failureThreshold'] : null,
        breakerRecoveryTimeoutSec: isNumber(circuitBreaker?.['recoveryTimeoutSec']) ? circuitBreaker['recoveryTimeoutSec'] : null,
        breakerWasEnabled: circuitBreaker?.['wasEnabled'] === true || candidate['circuitBreakerWasEnabled'] === true,
        maxConcurrentRequests: isNumber(technical?.['maxConcurrentRequests']) ? technical['maxConcurrentRequests'] : null
    });
};

export { stablePluginFingerprint };
