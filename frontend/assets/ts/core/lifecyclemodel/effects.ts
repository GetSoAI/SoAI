/* SoAI - Shared lifecycle model effects [frontend/assets/ts/core/lifecyclemodel/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { DeclaredResourcesHost, EnsureStreamResourcesOptions, ResourceSnapshot, ResourceState, StreamResourcesHost, StreamRuntimeOwners } from '@core/lifecyclemodel/types.ts';

const TAG = 'LifecycleModel';

const publishResourceDeclarationFailure = (moduleId: string, resources: string[]): void => {
    telemetry.publishMetric('lifecycle.ensureDeclaredResources.failed', 1, {
        module: moduleId || TAG,
        resources: isArray(resources) && resources.length ? resources.join(',') : 'none'
    });
};

const normalizeResourceState = (value: JsonValue | ResourceSnapshot | null | undefined): ResourceState | null => {
    if (!isObject(value)) {
        return null;
    }
    const statusValue = 'status' in value ? value.status : null;
    const errorValue = 'error' in value ? value.error : null;
    const state: ResourceState = {};
    if (isString(statusValue) && statusValue.trim()) {
        state.status = statusValue;
    }
    if (errorValue instanceof Error) {
        state.error = errorValue;
    } else if (isObject(errorValue)) {
        const nameValue = errorValue['name'];
        const messageValue = errorValue['message'];
        const errorObject: { name?: string; message?: string } = {};
        if (isString(nameValue) && nameValue.trim()) {
            errorObject.name = nameValue;
        }
        if (isString(messageValue) && messageValue.trim()) {
            errorObject.message = messageValue;
        }
        if (Object.keys(errorObject).length) {
            state.error = errorObject;
        }
    }
    return state;
};

const ensureLifecycleDeclaredResources = async (host: DeclaredResourcesHost, options: EnsureStreamResourcesOptions = {}): Promise<StreamRuntimeOwners | null> => {
    const requiredResources = host.getRequiredResources();
    const resources = isArray(requiredResources) ? requiredResources.filter(Boolean) : [];
    if (!resources.length) {
        return null;
    }
    const existingPromise = host.getDeclaredResourcesPromise();
    if (existingPromise) {
        return existingPromise;
    }
    let declarationPromise!: Promise<StreamRuntimeOwners | null>;
    declarationPromise = (async (): Promise<StreamRuntimeOwners | null> => {
        try {
            return await host.ensureStreamResources(resources, options);
        } catch (error) {
            publishResourceDeclarationFailure(host.getLifecycleIdentifier(), resources);
            throw error;
        } finally {
            host.clearDeclaredResourcesPromise(declarationPromise);
        }
    })();
    host.setDeclaredResourcesPromise(declarationPromise);
    return declarationPromise;
};

const ensureLifecycleStreamResources = async (host: StreamResourcesHost, resourceNames: string | string[], options?: EnsureStreamResourcesOptions): Promise<StreamRuntimeOwners> => {
    const resources = isArray(resourceNames) ? resourceNames.filter(Boolean) : resourceNames ? [resourceNames] : [];
    const uniqueResources = [...new Set(resources)];
    const allowDiscovery = options?.allowDiscovery ?? true;
    const signal = options?.signal;
    const strict = options?.strict ?? false;

    const manager = await host.getStreamManager({
        ensureReady: false,
        allowDiscovery,
        signal
    });
    if (!uniqueResources.length) {
        return manager;
    }

    const readResourceState = (resourceName: string): ResourceState | null => {
        if (!resourceName) {
            return null;
        }
        const value = manager.resources.getResource(resourceName, { state: true });
        return normalizeResourceState(value);
    };

    const waitForReadyState = async (resourceName: string): Promise<ResourceState | ResourceSnapshot | null> => {
        if (!resourceName) {
            return null;
        }
        const currentState = readResourceState(resourceName);
        if (currentState?.status === 'ready') {
            return currentState;
        }
        if (currentState?.status === 'error') {
            throw currentState.error || new Error(`Resource ${resourceName} failed to start`);
        }
        return new Promise((resolve, reject) => {
            let unsubscribe = (): void => {};
            const cleanup = (): void => {
                unsubscribe();
                unsubscribe = (): void => {};
                signal?.removeEventListener('abort', onAbort);
            };
            const onAbort = (): void => {
                cleanup();
                reject(createAbortError());
            };

            if (signal?.aborted) {
                onAbort();
                return;
            }
            signal?.addEventListener('abort', onAbort, { once: true });

            const result = manager.subscriptions.subscribeResourceState(
                resourceName,
                (snapshot: ResourceSnapshot) => {
                    if (!snapshot || snapshot.name !== resourceName) {
                        return;
                    }
                    if (snapshot.status === 'ready') {
                        cleanup();
                        resolve(snapshot);
                    } else if (snapshot.status === 'error') {
                        cleanup();
                        reject(snapshot.error || new Error(`Resource ${resourceName} failed to start`));
                    }
                },
                { immediate: false, ensureStart: true }
            );
            unsubscribe = result;
        });
    };

    const startResource = (resourceName: string): Promise<JsonValue | null | undefined> | null => {
        if (!resourceName) {
            return null;
        }
        return manager.resources.ensureResourceStarted(resourceName);
    };

    const startTasks: Promise<JsonValue | null | undefined>[] = [];
    for (const resourceName of uniqueResources) {
        const task = startResource(resourceName);
        if (task) {
            startTasks.push(task);
        }
    }

    if (strict) {
        if (startTasks.length) {
            await Promise.all(startTasks);
        }
        await Promise.all(uniqueResources.map((resourceName) => waitForReadyState(resourceName)));
        return manager;
    }

    if (startTasks.length) {
        await Promise.all(
            startTasks.map(async (task, index) => {
                try {
                    await task;
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug(TAG, `Resource ensure failed for ${uniqueResources[index]}`, runtimeError);
                }
            })
        );
    }
    return manager;
};

export { ensureLifecycleDeclaredResources, ensureLifecycleStreamResources };
