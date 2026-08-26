/* SoAI - Search feature panel effects [frontend/assets/ts/features/search/panel/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { HARDWARE, MODELS, PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { SEARCH_SOURCE_HARDWARE } from '@core/search/protocols.ts';
import { extractCollection, normalizeModelForIndex, normalizePluginForIndex } from '@core/search/searchResultNormalization.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { type JsonValue, isJsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFunction, isObject, isPlainObject } from '@core/typeGuards.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import type { SearchBackendDependencies, SearchIndexKey } from '@features/search/panel/contracts.ts';
import type { SearchBackendState } from '@features/search/panel/state.ts';

interface SearchReadinessContext {
    dependencies: SearchBackendDependencies;
    state: SearchBackendState;
    isActive: () => boolean;
    onSystemReady: () => void;
}

interface SearchStreamContext {
    dependencies: SearchBackendDependencies;
    state: SearchBackendState;
    isActive: () => boolean;
    updateSearchIndex: (type: SearchIndexKey, items: SearchItem[]) => void;
}

type HardwareSnapshotRequest = (resource: string) => Promise<JsonValue>;

const updateIndexesFromContributors = (context: SearchStreamContext, source: string, resourceValue: JsonValue): void => {
    for (const contributor of context.dependencies.searchContributors) {
        if (contributor.source !== source) {
            continue;
        }
        context.updateSearchIndex(contributor.bucket, contributor.index(resourceValue));
    }
};

const markSystemReady = (context: SearchReadinessContext): void => {
    if (!context.isActive() || context.state.systemReady) {
        return;
    }
    context.state.systemReady = true;
    context.onSystemReady();
};

const ensureApiReady = async (context: SearchReadinessContext): Promise<void> => {
    await context.dependencies.apiClient.whenReady({ allowDiscovery: true });
};

const monitorSystemReadiness = async (context: SearchReadinessContext): Promise<void> => {
    if (context.state.systemReady) {
        return;
    }
    if (context.state.systemReadyPromise) {
        return await context.state.systemReadyPromise;
    }

    const task = (async () => {
        try {
            const monitor = context.dependencies.connectionStatus;
            const subscription = monitor.subscribe(
                (event) => {
                    if (event.systemInfo) {
                        markSystemReady(context);
                    }
                },
                { emitCurrent: true }
            );
            context.dependencies.trackResource(subscription);
            const snapshot = isFunction(monitor.getSnapshot) ? monitor.getSnapshot() : null;
            if (snapshot?.systemInfo) {
                markSystemReady(context);
                return;
            }
            try {
                if ((await monitor.getInitialSnapshot({ timeout: 3500 }))?.systemInfo) {
                    markSystemReady(context);
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('SearchPanel', 'Initial system snapshot unavailable', runtimeError);
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('SearchPanel', 'Failed to monitor system readiness', runtimeError);
            throw runtimeError;
        }
    })();

    context.state.systemReadyPromise = task;
    await task;
    if (context.state.systemReady) {
        context.state.systemReadyPromise = null;
    }
};

const waitForSystemReady = async (context: SearchReadinessContext, timeout: number = 3000): Promise<boolean> => {
    if (context.state.systemReady) {
        return true;
    }
    try {
        await monitorSystemReadiness(context);
        if ((await context.dependencies.connectionStatus.getInitialSnapshot({ timeout }))?.systemInfo) {
            markSystemReady(context);
            return true;
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('SearchPanel', 'System readiness wait timed out', runtimeError);
    }
    return context.state.systemReady;
};

const updateModelIndex = (context: SearchStreamContext, value: JsonValue | null | undefined): void => {
    context.updateSearchIndex(
        'models',
        extractCollection(value)
            .map((item) => normalizeModelForIndex(item))
            .filter((entry): entry is SearchItem => entry !== null)
    );
};

const updatePluginIndex = (context: SearchStreamContext, value: JsonValue | null | undefined): void => {
    context.updateSearchIndex(
        'plugins',
        extractCollection(value)
            .map((item) => normalizePluginForIndex(item))
            .filter((entry): entry is SearchItem => entry !== null)
    );
};

const hydrateHardwareIndexFromSnapshot = async (context: SearchStreamContext, requestSnapshot: HardwareSnapshotRequest): Promise<void> => {
    if (!context.state.grantedActions.has('HARDWARE_READ')) {
        context.updateSearchIndex('devices', []);
        return;
    }
    try {
        const snapshot = await requestSnapshot(HARDWARE);
        updateIndexesFromContributors(context, SEARCH_SOURCE_HARDWARE, snapshot);
    } catch (error) {
        errorHandler.debug('SearchPanel', 'Hardware search snapshot unavailable', ensureError(error));
    }
};

const pushSearchSubscription = (subscriptions: Array<() => void>, unsubscribe: (() => void) | null): void => {
    if (isFunction(unsubscribe)) {
        subscriptions.push(unsubscribe);
        return;
    }
    for (const subscription of subscriptions) {
        subscription();
    }
    throw new Error('Search collection resource subscription is invalid');
};

const primeDataResources = async (context: SearchStreamContext): Promise<void> => {
    if (context.state.collectionsPrimedPromise) {
        return await context.state.collectionsPrimedPromise;
    }
    const task = subscribeToDataStreams(context);
    context.state.collectionsPrimedPromise = task;
    try {
        return await task;
    } catch (error) {
        context.state.collectionsPrimedPromise = null;
        throw error;
    }
};

const subscribeToDataStreams = async (context: SearchStreamContext, requestSnapshot: HardwareSnapshotRequest = requestWebSocketSnapshotRecord): Promise<void> => {
    if (context.state.streamSubscriptionsRegistered) {
        return;
    }
    if (context.state.streamSubscriptionTask) {
        return await context.state.streamSubscriptionTask;
    }

    let task: Promise<void> | null = null;
    task = (async () => {
        try {
            const manager = await context.dependencies.getStreamManager({
                ensureReady: false,
                allowDiscovery: true
            });
            if (!context.isActive()) {
                return;
            }
            const subscriptions: Array<() => void> = [];
            pushSearchSubscription(
                subscriptions,
                manager.subscriptions.subscribeResourceState(
                    MODELS,
                    (snapshot) => {
                        if (snapshot.status === 'ready') updateModelIndex(context, snapshot.value);
                    },
                    { immediate: true, ensureStart: false }
                )
            );
            pushSearchSubscription(
                subscriptions,
                manager.subscriptions.subscribeResourceState(
                    PLUGINS,
                    (snapshot) => {
                        if (snapshot.status === 'ready') updatePluginIndex(context, snapshot.value);
                    },
                    { immediate: true, ensureStart: false }
                )
            );
            context.dependencies.trackResource(() => {
                for (const subscription of subscriptions) {
                    subscription();
                }
            });
            await Promise.all([manager.resources.ensureResourceStarted(MODELS, { allowDiscovery: true, throwOnError: false }), manager.resources.ensureResourceStarted(PLUGINS, { allowDiscovery: true, throwOnError: false }), hydrateHardwareIndexFromSnapshot(context, requestSnapshot)]).catch((error) => {
                const runtimeError = ensureError(error);
                if (!isAbortError(runtimeError)) {
                    errorHandler.warn('SearchPanel', 'Search collection resource readiness failed', runtimeError);
                }
            });
            if (context.isActive()) {
                context.state.streamSubscriptionsRegistered = true;
            }
        } catch (error) {
            context.state.streamSubscriptionsRegistered = false;
            throw error;
        } finally {
            if (context.state.streamSubscriptionTask === task) {
                context.state.streamSubscriptionTask = null;
            }
        }
    })();

    context.state.streamSubscriptionTask = task;
    await task;
};

const hydrateIndexFromResources = (context: SearchStreamContext): void => {
    const streamManager = context.dependencies.peekStreamManager({ required: false });
    if (!streamManager) return;

    const resolveResource = (name: string): JsonValue | null | undefined => {
        const state = streamManager.resources.getResource(name, { state: true });
        if (state && isObject(state) && hasOwn(state, 'value')) {
            const value = state['value'];
            return isJsonValue(value) ? value : null;
        }
        const resource = streamManager.resources.getResource(name, {});
        return isJsonValue(resource) ? resource : null;
    };

    const models = resolveResource(MODELS);
    if (isObject(models) || Array.isArray(models)) {
        context.updateSearchIndex(
            'models',
            extractCollection(models)
                .map((item) => normalizeModelForIndex(item))
                .filter((entry): entry is SearchItem => entry !== null)
        );
    }

    const plugins = resolveResource(PLUGINS);
    if (isObject(plugins) || Array.isArray(plugins)) {
        context.updateSearchIndex(
            'plugins',
            extractCollection(plugins)
                .map((item) => normalizePluginForIndex(item))
                .filter((entry): entry is SearchItem => entry !== null)
        );
    }

    const hardware = resolveResource(HARDWARE);
    updateIndexesFromContributors(context, SEARCH_SOURCE_HARDWARE, isPlainObject(hardware) ? hardware : null);
};

export { ensureApiReady, monitorSystemReadiness, waitForSystemReady, primeDataResources, subscribeToDataStreams, hydrateIndexFromResources, markSystemReady };
