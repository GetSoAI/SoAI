/* SoAI - Tasks feature task operation API controller [frontend/assets/ts/features/tasks/taskmanager/TaskOperationApiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskLocalOperationUpdate, TaskOperationEntry, TaskOperationFilter, TaskOperationListener, TaskOperationMeta, TaskOperationsApi } from '@core/tasks/protocols.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { TaskManagerActions } from '@features/tasks/taskmanager/TaskManagerActions.ts';
import { filterTaskOperations } from '@features/tasks/taskmanager/operationFiltering.ts';
import type { TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface TaskOperationApiControllerDependencies {
    store: TaskManagerStoreApi;
    actions: TaskManagerActions;
}

class TaskOperationApiController implements TaskOperationsApi {
    readonly #store: TaskManagerStoreApi;
    readonly #actions: TaskManagerActions;
    readonly #localCancelHandlers = new Map<string, () => void | Promise<void>>();
    readonly #localOperationMeta = new Map<string, TaskOperationEntry>();

    constructor(dependencies: TaskOperationApiControllerDependencies) {
        this.#store = dependencies.store;
        this.#actions = dependencies.actions;
    }

    getOperations(filter: TaskOperationFilter = {}): TaskOperationEntry[] {
        const operations = this.#mergeLocalOperationMeta(this.#store.getActiveOperations());
        this.#pruneLocalCancelHandlers(operations);
        return filterTaskOperations(operations, filter, (source) => this.#store.getPluginKey(source));
    }

    subscribeOperations(filter: TaskOperationFilter, listener: TaskOperationListener): () => void {
        if (!isFunction(listener)) {
            throw new Error('TaskManager operation subscription requires a listener');
        }
        listener(this.getOperations(filter));
        return this.#store.subscribe(() => {
            listener(this.getOperations(filter));
        });
    }

    async reconcileOperations(): Promise<void> {
        await this.#store.reconcileOperations();
    }

    async cancelOperationById(operationId: string): Promise<void> {
        const operation = this.#store.getOperationById(operationId);
        if (!operation) {
            this.#localCancelHandlers.delete(operationId);
            this.#localOperationMeta.delete(operationId);
            return;
        }
        if (operation.cancelable !== true) {
            return;
        }
        const localCancel = this.#localCancelHandlers.get(operationId);
        if (localCancel) {
            await localCancel();
            return;
        }
        await this.#actions.cancelOperation(operation);
    }

    getPluginKey(source: string | null | undefined): string | null {
        return this.#store.getPluginKey(source);
    }

    upsertLocalOperation(update: TaskLocalOperationUpdate): void {
        if (!isObject(update) || !isString(update.id) || !update.id.trim() || !isString(update.type) || !update.type.trim()) {
            throw new Error('TaskManager local operation requires id and type');
        }
        const operationId = update.id.trim();
        const pluginName = isString(update.pluginName) && update.pluginName.trim() ? update.pluginName.trim() : null;
        const pluginKey = isString(update.pluginKey) && update.pluginKey.trim() ? update.pluginKey.trim().toLowerCase() : this.#store.getPluginKey(pluginName);
        const meta = isObject(update.meta) ? { ...update.meta } : {};
        if (update.cancelable !== false && isFunction(update.cancel)) {
            this.#localCancelHandlers.set(operationId, update.cancel);
        } else {
            this.#localCancelHandlers.delete(operationId);
        }
        if (pluginName) {
            meta['plugin'] = pluginName;
            meta['pluginName'] = pluginName;
        }
        const localOperation: TaskOperationEntry = {
            id: operationId,
            type: update.type.trim(),
            ...(pluginKey ? { pluginKey } : {}),
            ...(pluginName ? { pluginName: pluginName } : {}),
            meta: this.#buildLocalOperationMeta(meta),
            cancelable: update.cancelable !== false
        };
        this.#localOperationMeta.set(operationId, localOperation);
        const existingOperation = this.#store.getOperationById(operationId);
        if (existingOperation && existingOperation.isLocal !== true) {
            this.#store.upsertOperation(existingOperation);
            return;
        }
        this.#store.upsertOperation({
            id: operationId,
            type: update.type.trim(),
            ...(pluginKey ? { pluginKey } : {}),
            ...(pluginName ? { pluginName: pluginName } : {}),
            meta,
            cancelable: update.cancelable !== false,
            progress: this.#store.normalizeProgress(update.progress),
            isLocal: true
        });
        if (!this.#store.getOperationById(operationId)) {
            this.#localCancelHandlers.delete(operationId);
            this.#localOperationMeta.delete(operationId);
        }
    }

    removeLocalOperation(operationId: string): void {
        const operation = this.#store.getOperationById(operationId);
        const shouldRemoveStoreOperation = operation?.isLocal === true;
        this.#localCancelHandlers.delete(operationId);
        this.#localOperationMeta.delete(operationId);
        if (shouldRemoveStoreOperation) {
            this.#store.removeOperationById(operationId);
        } else if (operation) {
            this.#store.upsertOperation(operation);
        }
    }

    #pruneLocalCancelHandlers(operations: readonly TaskOperationEntry[]): void {
        if (this.#localCancelHandlers.size === 0 && this.#localOperationMeta.size === 0) {
            return;
        }
        const activeOperationIds = new Set(operations.map((operation) => operation.id));
        for (const operationId of this.#localCancelHandlers.keys()) {
            if (!activeOperationIds.has(operationId)) {
                this.#localCancelHandlers.delete(operationId);
            }
        }
        for (const operationId of this.#localOperationMeta.keys()) {
            if (!activeOperationIds.has(operationId)) {
                this.#localOperationMeta.delete(operationId);
            }
        }
    }

    #mergeLocalOperationMeta(operations: readonly TaskOperationEntry[]): TaskOperationEntry[] {
        if (this.#localOperationMeta.size === 0) {
            return [...operations];
        }
        return operations.map((operation) => {
            const localMeta = this.#localOperationMeta.get(operation.id);
            if (!localMeta) {
                return operation;
            }
            return {
                ...operation,
                ...(localMeta.pluginKey ? { pluginKey: localMeta.pluginKey } : {}),
                ...(localMeta.pluginName ? { pluginName: localMeta.pluginName } : {}),
                meta: { ...(operation.meta ?? {}), ...(localMeta.meta ?? {}) },
                cancelable: operation.cancelable === true || localMeta.cancelable === true
            };
        });
    }

    #buildLocalOperationMeta(meta: TaskOperationMeta): TaskOperationMeta {
        const localMeta: TaskOperationMeta = {};
        for (const key of ['plugin', 'pluginName', 'convId', 'ownerType', 'ownerId', 'displayName']) {
            const value = meta[key];
            if (value !== undefined && value !== null) {
                localMeta[key] = value;
            }
        }
        return localMeta;
    }
}

export { TaskOperationApiController };
