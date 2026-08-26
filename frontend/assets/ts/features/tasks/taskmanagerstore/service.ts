/* SoAI - Tasks feature task manager store service [frontend/assets/ts/features/tasks/taskmanagerstore/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { normalizeProgress } from '@core/primitives/progress.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { OperationDefinition, OperationEntry, PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';
import { getActiveOperationCount, getActiveOperations, getActivePluginCount, getActivePlugins, getBlockingPluginCount, getCancelableOperations, getCancelableOperationsForPluginKey, getOperationById, getOperationCountForPlugin, getOperationDefinition, getPlugins, getStoppablePlugins, hasBlockingActivity, isActiveStatus, isPersistentStatus, shouldShowProgress } from '@features/tasks/taskmanagerstore/actions.ts';
import type { TaskManagerStoreDependencies } from '@features/tasks/taskmanagerstore/contracts.ts';
import { reconcileOperations, setupOperationTracking, subscribeToPlugins } from '@features/tasks/taskmanagerstore/effects.ts';
import { toUpperCaseValue } from '@features/tasks/taskmanagerstore/guards.ts';
import { createTaskManagerStoreState, type Listener } from '@features/tasks/taskmanagerstore/state.ts';

class TaskManagerStore extends LifecycleModel implements TaskManagerStoreApi {
    #dependencies: TaskManagerStoreDependencies;
    #state = createTaskManagerStoreState();

    constructor(dependencies: TaskManagerStoreDependencies) {
        super({ name: 'TaskManagerStore', type: 'store' });
        if (!dependencies?.stream) {
            throw new Error('TaskManagerStore requires stream owners');
        }
        this.#dependencies = dependencies;
    }

    subscribe(listener: Listener): () => void {
        if (!isFunction(listener)) {
            throw new Error('TaskManagerStore subscribe requires a listener');
        }
        this.#state.listeners.add(listener);
        return () => {
            this.#state.listeners.delete(listener);
        };
    }

    #notify(): void {
        if (this.#state.listeners.size) {
            for (const listener of this.#state.listeners) {
                try {
                    listener(this);
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.debug('TaskManagerStore', 'State listener failed', runtimeError);
                }
            }
        }
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) await this.destroy();
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        this.#state.lifecycleGeneration += 1;
        this.#state.operationSubscriptionTask = null;
        this.#state.operationReconciliationTask = null;
        const lifecycleGeneration = this.#state.lifecycleGeneration;
        const isCurrentLifecycle = (): boolean => this.#state.lifecycleGeneration === lifecycleGeneration;
        await subscribeToPlugins({
            dependencies: this.#dependencies,
            state: this.#state,
            pluginKey: (source) => this.#pluginKey(source),
            isActiveStatus: (status) => this.isActiveStatus(status),
            getOperationDefinition: (type) => this.getOperationDefinition(type),
            normalizeProgress: (value) => normalizeProgress(value),
            isCurrentLifecycle,
            notify: () => this.#notify(),
            trackDisposable: (resource, onDispose) => this.lifecycleResources.track(resource, onDispose),
            untrackOperationSubscription: (unsubscribe) => this.resources?.untrack?.(unsubscribe)
        });
        if (!isCurrentLifecycle()) {
            return;
        }
        await setupOperationTracking({
            dependencies: this.#dependencies,
            state: this.#state,
            pluginKey: (source) => this.#pluginKey(source),
            isActiveStatus: (status) => this.isActiveStatus(status),
            getOperationDefinition: (type) => this.getOperationDefinition(type),
            normalizeProgress: (value) => normalizeProgress(value),
            isCurrentLifecycle,
            notify: () => this.#notify(),
            trackDisposable: (resource, onDispose) => this.lifecycleResources.track(resource, onDispose),
            untrackOperationSubscription: (unsubscribe) => this.resources?.untrack?.(unsubscribe)
        });
        if (!isCurrentLifecycle()) {
            return;
        }
        await this.reconcileOperations();
        if (!isCurrentLifecycle()) {
            return;
        }
        this.#notify();
    }

    async reconcileOperations(): Promise<void> {
        if (this.#state.operationReconciliationTask) {
            return this.#state.operationReconciliationTask;
        }
        const lifecycleGeneration = this.#state.lifecycleGeneration;
        const isCurrentLifecycle = (): boolean => this.#state.lifecycleGeneration === lifecycleGeneration;
        const task = reconcileOperations({
            dependencies: this.#dependencies,
            state: this.#state,
            pluginKey: (source) => this.#pluginKey(source),
            isActiveStatus: (status) => this.isActiveStatus(status),
            getOperationDefinition: (type) => this.getOperationDefinition(type),
            normalizeProgress: (value) => normalizeProgress(value),
            isCurrentLifecycle,
            notify: () => this.#notify(),
            trackDisposable: (resource, onDispose) => this.lifecycleResources.track(resource, onDispose),
            untrackOperationSubscription: (unsubscribe) => this.resources?.untrack?.(unsubscribe)
        }).finally(() => {
            if (isCurrentLifecycle()) {
                this.#state.operationReconciliationTask = null;
            }
        });
        this.#state.operationReconciliationTask = task;
        return task;
    }

    override async onDestroy(): Promise<void> {
        this.#state.lifecycleGeneration += 1;
        const pluginSub = this.#state.pluginSubscription;
        if (pluginSub) {
            try {
                if (isFunction(pluginSub.abort)) pluginSub.abort();
                else if (isFunction(pluginSub.unsubscribe)) pluginSub.unsubscribe();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('TaskManagerStore', 'Plugin subscription cleanup failed', runtimeError);
            }
            this.#state.pluginSubscription = null;
        }

        const opUnsub = this.#state.operationUnsubscribe;
        if (isFunction(opUnsub)) {
            try {
                opUnsub();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('TaskManagerStore', 'Operation unsubscribe failed', runtimeError);
            }
            this.resources?.untrack?.(opUnsub);
        }
        this.#state.operationUnsubscribe = null;
        this.#state.operationSubscriptionTask = null;
        this.#state.operationReconciliationTask = null;
        this.#state.plugins = [];
        this.#state.activePlugins = [];
        this.#state.pluginSnapshotSignature = '';
        this.#state.operations.clear();
        this.#state.terminalTaskIds.clear();
        this.#state.catalogNetworkFaultActive = false;
        this.#notify();
    }

    getPlugins(): PluginEntry[] {
        return getPlugins(this.#state);
    }
    getActivePlugins(): PluginEntry[] {
        return getActivePlugins(this.#state);
    }

    getStoppablePlugins(): PluginEntry[] {
        return getStoppablePlugins(this.#state, (plugin) => plugin.isPersistent === true || this.isPersistentStatus(plugin.state || null));
    }

    getStoppableCount(): number {
        return this.getStoppablePlugins().length;
    }
    getActiveOperations(): OperationEntry[] {
        return getActiveOperations(this.#state);
    }
    getActiveOperationCount(): number {
        return getActiveOperationCount(this.#state);
    }
    getCancelableOperations(): OperationEntry[] {
        return getCancelableOperations(this.#state);
    }

    getCancelableOperationsForPluginKey(key: string | null | undefined): OperationEntry[] {
        return getCancelableOperationsForPluginKey(this.#state, key);
    }

    getActivePluginCount(): number {
        return getActivePluginCount(this.#state, (plugin) => this.#pluginKey(plugin));
    }

    getBlockingPluginCount(): number {
        return getBlockingPluginCount(this.#state, toUpperCaseValue);
    }

    hasBlockingActivity(): boolean {
        return hasBlockingActivity(this.#state, toUpperCaseValue);
    }

    getOperationsForPlugin(plugin: PluginEntry | string): OperationEntry[] {
        return getOperationCountForPlugin(this.#state, plugin, (source) => this.#pluginKey(source));
    }

    getOperationById(id: string | null | undefined): OperationEntry | null {
        return getOperationById(this.#state, id);
    }

    removeOperationById(id: string | null | undefined): OperationEntry | null {
        if (!isString(id)) {
            return null;
        }

        const operation = this.#state.operations.get(id);
        if (!operation) {
            return null;
        }

        this.#state.operations.delete(id);
        this.#notify();
        return operation;
    }

    upsertOperation(operation: OperationEntry | null | undefined): void {
        if (operation?.id && !this.#state.terminalTaskIds.has(operation.id)) {
            this.#state.operations.set(operation.id, operation);
            this.#notify();
        }
    }

    getOperationDefinition(type: string | null | undefined): OperationDefinition | null {
        return getOperationDefinition(type);
    }

    isActiveStatus(status: string | null | undefined): boolean {
        return isActiveStatus(status, toUpperCaseValue);
    }

    isPersistentStatus(status: string | null | undefined): boolean {
        return isPersistentStatus(status, toUpperCaseValue);
    }

    shouldShowProgress(status: string | null | undefined): boolean {
        return shouldShowProgress(status, toUpperCaseValue);
    }

    normalizeProgress(value: JsonValue | null | undefined): number {
        return normalizeProgress(value) ?? 0;
    }

    getPluginKey(source: PluginEntry | string | null | undefined): string | null {
        return this.#pluginKey(source);
    }
    resolvePluginDisplayName(plugin: PluginEntry): string {
        return this.#resolvePluginDisplayName(plugin);
    }

    #pluginKey(source: PluginEntry | string | null | undefined): string | null {
        if (!source) return null;
        if (isObject(source)) {
            const pluginKeyValue = source['__pluginKey'];
            if (isString(pluginKeyValue) && pluginKeyValue.trim()) return pluginKeyValue.trim();
        }
        const name = this.#normalizePluginName(source);
        return name ? name.toLowerCase() : null;
    }

    #normalizePluginName(source: PluginEntry | string | null | undefined): string | null {
        if (!source) return null;
        if (isString(source)) return source.trim() || null;
        if (isObject(source)) {
            return toTrimmedStringOrNull(source['name']) || toTrimmedStringOrNull(source.displayName) || toTrimmedStringOrNull(source['identifier']) || toTrimmedStringOrNull(source['plugin']);
        }
        return null;
    }

    #resolvePluginDisplayName(plugin: PluginEntry): string {
        const explicitName = toTrimmedStringOrNull(plugin?.name);
        if (plugin?.__synthetic && explicitName) return explicitName;
        const name = this.#normalizePluginName(plugin);
        if (!name) throw new Error('TaskManagerStore plugin entry missing display name.');
        return name;
    }
}

export { TaskManagerStore };
