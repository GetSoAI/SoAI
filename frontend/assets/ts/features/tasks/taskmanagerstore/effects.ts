/* SoAI - Tasks feature task manager store effects [frontend/assets/ts/features/tasks/taskmanagerstore/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { buildOperationUpdate } from '@features/tasks/taskmanagerstore/events.ts';
import { buildPluginSnapshotSignature, coercePluginEntries } from '@features/tasks/taskmanagerstore/mappers.ts';
import { handleTerminalTaskEvent } from '@features/tasks/taskmanagerstore/terminalEvents.ts';
import type { OperationDefinition, OperationEvent, PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { TaskManagerStoreDependencies } from '@features/tasks/taskmanagerstore/contracts.ts';
import type { TaskManagerStoreState } from '@features/tasks/taskmanagerstore/state.ts';

interface TaskManagerStoreEffectContext {
    state: TaskManagerStoreState;
    dependencies: TaskManagerStoreDependencies;
    pluginKey: (source: PluginEntry | string | null | undefined) => string | null;
    isActiveStatus: (status: string | null | undefined) => boolean;
    getOperationDefinition: (type: string | null | undefined) => OperationDefinition | null;
    normalizeProgress: (value: JsonValue | null | undefined) => number | null;
    isCurrentLifecycle: () => boolean;
    notify: () => void;
    trackDisposable: <T extends DisposableResource>(resource: T, onDispose?: ((resource: T) => void) | undefined) => void;
    untrackOperationSubscription: (unsubscribe: (() => void) | null | undefined) => void;
}

const updatePlugins = (context: TaskManagerStoreEffectContext, rawPlugins: PluginEntry[]): void => {
    const plugins = rawPlugins;
    const signature = buildPluginSnapshotSignature(plugins, {
        pluginKey: (source) => context.pluginKey(source)
    });

    if (signature === context.state.pluginSnapshotSignature) {
        return;
    }

    context.state.pluginSnapshotSignature = signature;
    context.state.plugins = plugins;
    context.state.activePlugins = plugins.filter((plugin) => context.isActiveStatus(plugin.state));
    context.notify();
};

const handleCatalogRecovered = (context: TaskManagerStoreEffectContext): void => {
    if (context.state.catalogNetworkFaultActive) {
        context.state.catalogNetworkFaultActive = false;
        errorHandler.info('TaskManagerStore', 'Plugin catalog connection restored');
    }
};

const handleCatalogNetworkError = (context: TaskManagerStoreEffectContext, error: Error): void => {
    if (!context.state.catalogNetworkFaultActive) {
        context.state.catalogNetworkFaultActive = true;
        errorHandler.warn('TaskManagerStore', 'Plugin catalog offline', error);
    }
};

const subscribeToPlugins = async (context: TaskManagerStoreEffectContext): Promise<void> => {
    try {
        const manager = context.dependencies.stream;
        if (!context.isCurrentLifecycle()) {
            return;
        }
        const previousSubscription = context.state.pluginSubscription;
        if (previousSubscription) {
            try {
                if (isFunction(previousSubscription.abort)) previousSubscription.abort();
                else if (isFunction(previousSubscription.unsubscribe)) previousSubscription.unsubscribe();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('TaskManagerStore', 'Previous plugin subscription cleanup failed', runtimeError);
            }
            context.state.pluginSubscription = null;
        }

        const unsubscribe = manager.subscriptions.subscribeResourceState(
            PLUGINS,
            (snapshot) => {
                if (!context.isCurrentLifecycle()) {
                    return;
                }
                if (snapshot.status !== 'ready') {
                    if (snapshot.status === 'error') {
                        const resourceError = ensureError(snapshot.error ?? new Error('Plugin catalog resource failed'));
                        if (isNetworkError(resourceError)) {
                            handleCatalogNetworkError(context, resourceError);
                        }
                    }
                    return;
                }
                handleCatalogRecovered(context);
                updatePlugins(context, coercePluginEntries(snapshot.value));
            },
            { immediate: true, ensureStart: false }
        );
        if (!isFunction(unsubscribe)) {
            throw new Error('Plugin resource subscription is unavailable');
        }
        const ready = manager.resources.ensureResourceStarted(PLUGINS, { allowDiscovery: true, throwOnError: false }).then(() => undefined);
        const sub = { unsubscribe, ready };
        if (!context.isCurrentLifecycle()) {
            try {
                unsubscribe();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('TaskManagerStore', 'Stale plugin subscription cleanup failed', runtimeError);
            }
            return;
        }

        context.state.pluginSubscription = sub;
        context.trackDisposable(sub, () => {
            unsubscribe();
        });

        sub.ready.catch((error) => {
            if (!context.isCurrentLifecycle()) {
                return;
            }
            if (!isAbortError(error)) {
                if (isNetworkError(error)) handleCatalogNetworkError(context, error);
                else errorHandler.error('TaskManagerStore', 'Plugin catalog readiness failed', error);
            }
        });
    } catch (error) {
        if (!context.isCurrentLifecycle()) {
            return;
        }
        const runtimeError = ensureError(error);
        if (isNetworkError(runtimeError)) handleCatalogNetworkError(context, runtimeError);
        else errorHandler.error('TaskManagerStore', 'Unable to initialize plugin subscription', runtimeError);
    }
};

const setupOperationTracking = async (context: TaskManagerStoreEffectContext): Promise<void> => {
    if (context.state.operationSubscriptionTask) return;

    const task = (async () => {
        try {
            const manager = context.dependencies.stream;
            if (!context.isCurrentLifecycle()) return;
            const previousUnsubscribe = context.state.operationUnsubscribe;
            if (isFunction(previousUnsubscribe)) {
                try {
                    context.untrackOperationSubscription(previousUnsubscribe);
                    previousUnsubscribe();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TaskManagerStore', 'Previous operation subscription cleanup failed', runtimeError);
                }
                context.state.operationUnsubscribe = null;
            }

            const unsubscribe = manager.tasks.subscribeOperations((event) => {
                if (!context.isCurrentLifecycle()) {
                    return;
                }
                try {
                    handleOperationEvent(context, event);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TaskManagerStore', 'Operation event handler failed', runtimeError);
                }
            });
            const unsubscribeTerminalTasks = manager.tasks.subscribeTerminalTasks((event) => {
                if (!context.isCurrentLifecycle()) {
                    return;
                }
                try {
                    handleTerminalTaskEvent(context, event);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TaskManagerStore', 'Terminal task event handler failed', runtimeError);
                }
            });

            if (!isFunction(unsubscribe) || !isFunction(unsubscribeTerminalTasks)) {
                throw new Error('Stream manager operation subscriptions must return unsubscribe functions');
            }
            const unsubscribeOperations = (): void => {
                unsubscribe();
                unsubscribeTerminalTasks();
            };

            if (!context.isCurrentLifecycle()) {
                try {
                    unsubscribeOperations();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TaskManagerStore', 'Stale operation subscription cleanup failed', runtimeError);
                }
                return;
            }
            context.state.operationUnsubscribe = unsubscribeOperations;
            context.trackDisposable(unsubscribeOperations);
        } catch (error) {
            if (!context.isCurrentLifecycle()) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('TaskManagerStore', 'Unable to attach operation tracking', runtimeError);
        } finally {
            if (context.isCurrentLifecycle()) {
                context.state.operationSubscriptionTask = null;
            }
        }
    })();

    context.state.operationSubscriptionTask = task;
    return task;
};

const reconcileOperations = async (context: TaskManagerStoreEffectContext): Promise<void> => {
    try {
        const manager = context.dependencies.stream;
        if (!context.isCurrentLifecycle()) {
            return;
        }
        await manager.tasks.reconnectOperations();
    } catch (error) {
        if (!context.isCurrentLifecycle()) {
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.warn('TaskManagerStore', 'Unable to reconcile task operations', runtimeError);
    }
};

const handleOperationEvent = (context: TaskManagerStoreEffectContext, event: OperationEvent | null | undefined): void => {
    const update = buildOperationUpdate(event, {
        getDefinition: (type) => context.getOperationDefinition(type),
        getPluginKey: (name) => context.pluginKey(name),
        getExistingOperation: (id) => context.state.operations.get(id) || null,
        normalizeProgress: (value) => context.normalizeProgress(value)
    });

    if (update.action === 'remove') {
        context.state.operations.delete(update.id);
        context.notify();
        return;
    }

    if (update.action === 'upsert') {
        context.state.operations.set(update.operation.id, update.operation);
        context.notify();
    }
};

export { reconcileOperations, subscribeToPlugins, setupOperationTracking };
