/* SoAI - Catalog plugin type declarations [frontend/assets/ts/core/types/catalogPluginTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface IncompatibilityDetails {
    reason?: string;
    canOverride?: boolean;
    isOverridden?: boolean;
    message?: string;
    details?: PluginIncompatibilityContext;
}

interface PluginIncompatibilityContext extends JsonObject {
    requiredVersion?: string;
    detectedVersion?: string;
    requiredOs?: string[];
    detectedOs?: string | null;
    requiredGpu?: string[];
    detectedVendors?: string[];
    missingDependencies?: string[];
    declaredDependencies?: string[];
}

interface CompatibilityInfo {
    reason: string | null;
    canOverride: boolean;
    isOverridden: boolean;
    details: JsonObject;
    message: string;
    error: string;
    isCompatible: boolean;
    permanentlyDisabled: boolean;
}

interface CircuitBreakerRaw {
    state?: string;
    isOpen?: boolean;
    failureCount?: number;
    failureThreshold?: number;
    recoveryTimeoutSec?: number;
    lastFailureAtMs?: number;
    wasEnabled?: boolean;
}

interface CircuitBreakerInfo {
    state: string;
    isOpen: boolean;
    failureCount: number;
    failureThreshold: number;
    recoveryTimeoutSec: number;
    lastFailureAtMs: number;
    wasEnabled: boolean;
}

interface PluginCapabilities {
    supportsModelDeletion?: boolean;
    supportsModelDownload?: boolean;
    supportsProviderManagement?: boolean;
    supportsGpuBinding?: boolean;
    externalProviderMode?: string;
}

interface Plugin {
    name?: string;
    displayName?: string;
    state?: string;
    isEnabled?: boolean;
    isAvailable?: boolean;
    permanentlyDisabled?: boolean;
    isPersistent?: boolean;
    isBuiltin?: boolean;
    userEnabledOnce?: boolean;
    incompatibility?: IncompatibilityDetails;
    circuitBreaker?: CircuitBreakerRaw | CircuitBreakerInfo | null;
    circuitBreakerWasEnabled?: boolean;
    capabilities?: PluginCapabilities;
    compatibility?: CompatibilityInfo;
}

interface NormalizedPlugin {
    name?: string;
    state: string;
    fileStatus?: string | null;
    isEnabled: boolean;
    isAvailable: boolean;
    disabledReason?: string | null;
    permanentlyDisabled: boolean;
    compatibility: CompatibilityInfo;
    isPersistent: boolean;
    isBuiltin: boolean;
    userEnabledOnce: boolean;
    circuitBreaker: CircuitBreakerInfo | null;
    circuitBreakerWasEnabled: boolean;
    incompatibility?: IncompatibilityDetails;
    capabilities?: PluginCapabilities;
}

export type { CircuitBreakerInfo, CircuitBreakerRaw, CompatibilityInfo, IncompatibilityDetails, NormalizedPlugin, Plugin, PluginCapabilities, PluginIncompatibilityContext };
