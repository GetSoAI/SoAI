/* SoAI - Shared realtime register stream resource [frontend/assets/ts/core/realtime/streammanager/resources/registerStreamResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { identity, RESOURCE_CONFIG_KEYS } from '@core/realtime/streammanager/internals.ts';
import { unwrap } from '@core/realtime/streammanager/resources/normalizers.ts';
import { hasResourceSubscribers } from '@core/realtime/streammanager/resources/resourceActivationPolicy.ts';
import { ResourceReconciler } from '@core/realtime/streammanager/resources/resourceReconciler.ts';
import { rebindResourceTypedSubscriptions } from '@core/realtime/streammanager/resources/resourceTypedSubscriptions.ts';
import { projectReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceSnapshotProjection.ts';
import type { ResourceConfig, ResourceEntry, ResourceRegistrationConfig } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFunction } from '@core/typeGuards.ts';

interface RegisterStreamResourceOptions {
    module: string;
    name: string;
    options: ResourceRegistrationConfig;
    resources: Map<string, ResourceEntry>;
    isReady: boolean;
    attemptStartResource: (name: string) => Promise<JsonValue | null>;
}

const startRegisteredResource = (parameters: RegisterStreamResourceOptions): void => {
    parameters.attemptStartResource(parameters.name).catch((error) => {
        const runtimeError = ensureError(error);
        if (isLifecycleCancellationError(runtimeError)) {
            return;
        }
        errorHandler.warn(parameters.module, `Registered resource start failed for ${parameters.name}`, runtimeError);
    });
};

const registrationIsCurrent = (resource: ResourceEntry, config: ResourceConfig, reconciler: ResourceReconciler, configurationRevision: number): boolean => resource.config === config && resource.reconciler === reconciler && resource.configurationRevision === configurationRevision;

const registerStreamResource = (parameters: RegisterStreamResourceOptions): ResourceEntry => {
    const { name, options, resources, isReady } = parameters;

    const existing = resources.get(name) || null;
    const { autoStart, fetch, normalize, transform, initialValue, ...rest } = options;
    const normalizedInitialValue: JsonValue | null = initialValue === undefined ? null : initialValue;

    const config: ResourceConfig = Object.freeze({
        ...existing?.config,
        ...rest,
        autoStart: autoStart === undefined ? (existing?.config.autoStart ?? true) : autoStart,
        fetch: isFunction(fetch) ? fetch : existing?.config.fetch || null,
        normalize: isFunction(normalize) ? normalize : existing?.config.normalize || unwrap,
        transform: isFunction(transform) ? transform : existing?.config.transform || identity
    });

    const hasInitialValue = hasOwn(options, 'initialValue');
    const configChanged = !existing ? true : RESOURCE_CONFIG_KEYS.some((key) => config[key] !== existing.config[key]);

    if (existing) {
        const effectiveConfig = configChanged || hasInitialValue ? config : existing.config;
        if (configChanged || hasInitialValue) {
            const previousConfig = existing.config;
            const previousReconciler = existing.reconciler;
            const previousConfigurationRevision = existing.configurationRevision;
            const reconciler = new ResourceReconciler(name);
            try {
                if (hasInitialValue && normalizedInitialValue !== null) {
                    reconciler.seedInitialValue(normalizedInitialValue);
                }
            } catch (error) {
                reconciler.dispose();
                if (!registrationIsCurrent(existing, previousConfig, previousReconciler, previousConfigurationRevision)) return resources.get(name) ?? existing;
                throw error;
            }
            if (!registrationIsCurrent(existing, previousConfig, previousReconciler, previousConfigurationRevision)) {
                reconciler.dispose();
                return resources.get(name) ?? existing;
            }
            existing.config = config;
            existing.configurationRevision = previousConfigurationRevision + 1;
            const configurationRevision = existing.configurationRevision;
            existing.reconciliationUnsubscribe?.();
            existing.reconciliationUnsubscribe = null;
            existing.reconciler = reconciler;
            previousReconciler.dispose();
            if (!registrationIsCurrent(existing, config, reconciler, configurationRevision)) {
                reconciler.dispose();
                return resources.get(name) ?? existing;
            }
            projectReconciliationSnapshot(existing, reconciler.snapshot);
            rebindResourceTypedSubscriptions(existing);
            if (!registrationIsCurrent(existing, config, reconciler, configurationRevision)) return existing;
        }

        if (resources.get(name) === existing && existing.config === effectiveConfig && isReady && (effectiveConfig.autoStart || hasResourceSubscribers(existing)) && (configChanged || existing.status !== 'ready')) {
            startRegisteredResource(parameters);
        }
        return existing;
    }

    const entry: ResourceEntry = {
        name,
        value: null,
        status: 'unavailable',
        error: null,
        warning: false,
        maintenance: false,
        updatedAt: null,
        configurationRevision: 1,
        lastSnapshot: null,
        listeners: new Set(),
        typedSubscribers: new Set(),
        reconciler: new ResourceReconciler(name),
        get pendingStart(): true | null {
            return this.reconciler.reconciling ? true : null;
        },
        reconciliationUnsubscribe: null,
        config
    };

    try {
        if (hasInitialValue && normalizedInitialValue != null) {
            entry.reconciler.seedInitialValue(normalizedInitialValue);
            projectReconciliationSnapshot(entry, entry.reconciler.snapshot);
        }
    } catch (error) {
        entry.reconciler.dispose();
        const supersedingResource = resources.get(name);
        if (supersedingResource) return supersedingResource;
        throw error;
    }

    const supersedingResource = resources.get(name);
    if (supersedingResource) {
        entry.reconciler.dispose();
        return supersedingResource;
    }
    resources.set(name, entry);
    if (config.autoStart && isReady) {
        startRegisteredResource(parameters);
    }
    return entry;
};

export { registerStreamResource };
export type { RegisterStreamResourceOptions };
