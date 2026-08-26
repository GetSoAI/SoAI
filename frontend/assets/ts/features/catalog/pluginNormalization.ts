/* SoAI - Catalog feature plugin normalization [frontend/assets/ts/features/catalog/pluginNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toUpperCase } from '@core/normalize.ts';
import { isCircuitBreakerStateActive, normalizeCircuitBreakerState, requireActiveCircuitBreakerNumber } from '@core/plugins/circuitBreaker.ts';
import { PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_QUARANTINED, PLUGIN_STATUS_STOPPED, PLUGIN_STATUS_UNKNOWN } from '@core/state/pluginStatus.ts';
import { readFiniteNumberOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isString } from '@core/typeGuards.ts';
import { PROVIDER_MODE, resolveProviderMode, type ProviderModeValue } from '@core/plugins/providerMode.ts';
import type { CircuitBreakerInfo, CompatibilityInfo, NormalizedPlugin, Plugin } from '@core/types/catalogPluginTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const ensureNumber = (value: JsonValue | undefined): number => readFiniteNumberOrNullValue(value) ?? 0;

const normalizeDetails = (details: JsonValue | undefined): JsonObject => {
    if (!isJsonObject(details)) return {};
    return Object.fromEntries(Object.entries(details));
};

const normalizeCompatibility = (plugin: Plugin | null | undefined): CompatibilityInfo => {
    const declaredPermanentlyDisabled = plugin?.permanentlyDisabled === true;
    const raw = plugin?.incompatibility;
    if (!raw || !raw.reason) {
        const providedCompatibility = plugin?.compatibility;
        if (providedCompatibility?.reason) {
            const reason = toUpperCase(providedCompatibility.reason);
            const canOverride = providedCompatibility.canOverride === true;
            const isOverridden = providedCompatibility.isOverridden === true;
            const permanentlyDisabled = !isOverridden && (declaredPermanentlyDisabled || providedCompatibility.permanentlyDisabled === true || Boolean(reason && !canOverride));
            const isCompatible = !reason || isOverridden;
            const message = isString(providedCompatibility.message) ? providedCompatibility.message : '';
            return {
                reason,
                canOverride: canOverride,
                isOverridden: isOverridden,
                details: normalizeDetails(providedCompatibility.details),
                message,
                error: !isCompatible ? message || reason : '',
                isCompatible: isCompatible,
                permanentlyDisabled: permanentlyDisabled
            };
        }
        return {
            reason: null,
            canOverride: false,
            isOverridden: false,
            details: {},
            message: '',
            error: '',
            isCompatible: !declaredPermanentlyDisabled,
            permanentlyDisabled: declaredPermanentlyDisabled
        };
    }
    const reason = toUpperCase(raw.reason);
    const canOverride = raw.canOverride === true;
    const isOverridden = raw.isOverridden === true;
    const message = isString(raw.message) ? raw.message : '';
    const details = normalizeDetails(raw.details);
    const permanentlyDisabled = !isOverridden && (declaredPermanentlyDisabled || Boolean(reason && !canOverride));
    const isCompatible = !reason || isOverridden;
    const error = !isCompatible ? message || reason : '';
    return {
        reason,
        canOverride: canOverride,
        isOverridden: isOverridden,
        details,
        message,
        error,
        isCompatible: isCompatible,
        permanentlyDisabled: permanentlyDisabled
    };
};

const getPluginCompatibility = (plugin: Plugin | null | undefined): CompatibilityInfo => {
    if (!plugin) return normalizeCompatibility(null);
    return normalizeCompatibility(plugin);
};

function getCircuitBreakerInfo(plugin: Plugin & { circuitBreaker: NonNullable<Plugin['circuitBreaker']> }): CircuitBreakerInfo;
function getCircuitBreakerInfo(plugin: Plugin | null | undefined): CircuitBreakerInfo | null;
function getCircuitBreakerInfo(plugin: Plugin | null | undefined): CircuitBreakerInfo | null {
    if (!plugin) return null;
    const rawBreaker = plugin.circuitBreaker;
    if (!rawBreaker) return null;
    const rawState = rawBreaker.state;
    const normalizedState = normalizeCircuitBreakerState(rawState);
    const isOpen = rawBreaker.isOpen === true || normalizedState === 'open';
    const breakerActive = isCircuitBreakerStateActive(normalizedState, isOpen);
    const failureCount = breakerActive ? requireActiveCircuitBreakerNumber(rawBreaker.failureCount, 'failure_count') : ensureNumber(rawBreaker.failureCount);
    const failureThreshold = breakerActive ? requireActiveCircuitBreakerNumber(rawBreaker.failureThreshold, 'failure_threshold') : ensureNumber(rawBreaker.failureThreshold);
    const recoveryTimeout = breakerActive ? requireActiveCircuitBreakerNumber(rawBreaker.recoveryTimeoutSec, 'recovery_timeout_sec') : ensureNumber(rawBreaker.recoveryTimeoutSec);
    const lastFailureMs = ensureNumber(rawBreaker.lastFailureAtMs);
    const wasEnabled = rawBreaker.wasEnabled ?? plugin.circuitBreakerWasEnabled ?? plugin.isEnabled ?? false;
    return {
        state: normalizedState || rawState || '',
        isOpen: isOpen,
        failureCount: failureCount,
        failureThreshold: failureThreshold,
        recoveryTimeoutSec: recoveryTimeout,
        lastFailureAtMs: lastFailureMs,
        wasEnabled: Boolean(wasEnabled)
    };
}

const isPluginPermanentlyDisabled = (plugin: Plugin | null | undefined): boolean => {
    if (!plugin) return false;
    const compatibility = getPluginCompatibility(plugin);
    return compatibility.permanentlyDisabled === true;
};

const isCircuitBreakerActive = (plugin: Plugin | null | undefined): boolean => {
    const breaker = getCircuitBreakerInfo(plugin);
    if (breaker) {
        return isCircuitBreakerStateActive(breaker.state, breaker.isOpen);
    }
    return false;
};

function normalizePlugin(plugin: Plugin): Readonly<NormalizedPlugin>;
function normalizePlugin(plugin: null): null;
function normalizePlugin(plugin: undefined): undefined;
function normalizePlugin(plugin: Plugin | null | undefined): Readonly<NormalizedPlugin> | null | undefined;
function normalizePlugin(plugin: Plugin | null | undefined): Readonly<NormalizedPlugin> | null | undefined {
    if (!plugin) return plugin;
    const compatibility = getPluginCompatibility(plugin);
    const breakerInfo = getCircuitBreakerInfo(plugin);
    const name = plugin.name;
    const stateValue = toUpperCase(plugin.state || PLUGIN_STATUS_UNKNOWN) || PLUGIN_STATUS_UNKNOWN;
    const checkPlugin: Plugin = { compatibility };
    if (plugin.name !== undefined) checkPlugin.name = plugin.name;
    if (plugin.state !== undefined) checkPlugin.state = plugin.state;
    if (plugin.isEnabled !== undefined) checkPlugin.isEnabled = plugin.isEnabled;
    if (plugin.isAvailable !== undefined) checkPlugin.isAvailable = plugin.isAvailable;
    if (plugin.permanentlyDisabled !== undefined) checkPlugin.permanentlyDisabled = plugin.permanentlyDisabled;
    if (plugin.isPersistent !== undefined) checkPlugin.isPersistent = plugin.isPersistent;
    if (plugin.isBuiltin !== undefined) checkPlugin.isBuiltin = plugin.isBuiltin;
    if (plugin.circuitBreakerWasEnabled !== undefined) checkPlugin.circuitBreakerWasEnabled = plugin.circuitBreakerWasEnabled;
    if (plugin.incompatibility !== undefined) checkPlugin.incompatibility = plugin.incompatibility;
    if (plugin.circuitBreaker !== undefined) checkPlugin.circuitBreaker = plugin.circuitBreaker;
    if (plugin.capabilities !== undefined) checkPlugin.capabilities = plugin.capabilities;
    const permanentlyDisabled = isPluginPermanentlyDisabled(checkPlugin);
    const checkPluginWithState: Plugin = { ...checkPlugin, state: stateValue };
    if (breakerInfo !== null) checkPluginWithState.circuitBreaker = breakerInfo;
    const breakerActive = isCircuitBreakerActive(checkPluginWithState);
    const enabledCandidate = plugin.isEnabled ?? (stateValue !== PLUGIN_STATUS_DISABLED && stateValue !== PLUGIN_STATUS_INCOMPATIBLE);
    const normalizedBreaker = breakerInfo
        ? {
              ...breakerInfo,
              wasEnabled: breakerInfo.wasEnabled ?? enabledCandidate
          }
        : null;
    let nextState = stateValue;
    if (permanentlyDisabled) {
        nextState = PLUGIN_STATUS_INCOMPATIBLE;
    } else if (compatibility.isOverridden && nextState === PLUGIN_STATUS_INCOMPATIBLE) {
        nextState = PLUGIN_STATUS_STOPPED;
    } else if (breakerActive && nextState !== PLUGIN_STATUS_QUARANTINED) {
        nextState = PLUGIN_STATUS_QUARANTINED;
    }
    const enabled = permanentlyDisabled || breakerActive ? false : enabledCandidate && nextState !== PLUGIN_STATUS_INCOMPATIBLE;
    const result: NormalizedPlugin = {
        state: nextState,
        isEnabled: enabled,
        isAvailable: permanentlyDisabled ? false : (plugin.isAvailable ?? compatibility.isCompatible),
        permanentlyDisabled: permanentlyDisabled,
        compatibility,
        isPersistent: plugin.isPersistent ?? false,
        isBuiltin: plugin.isBuiltin ?? false,
        circuitBreaker: normalizedBreaker,
        circuitBreakerWasEnabled: normalizedBreaker?.wasEnabled ?? plugin.circuitBreakerWasEnabled ?? enabledCandidate
    };
    if (name !== undefined) result.name = name;
    if (plugin.incompatibility !== undefined) result.incompatibility = plugin.incompatibility;
    if (plugin.capabilities !== undefined) result.capabilities = plugin.capabilities;
    return Object.freeze(result);
}

export { getPluginCompatibility, getCircuitBreakerInfo, isPluginPermanentlyDisabled, isCircuitBreakerActive, normalizePlugin, resolveProviderMode, PROVIDER_MODE };
export type ProviderMode = ProviderModeValue;
export type { CompatibilityInfo, CircuitBreakerInfo, ProviderModeValue };
