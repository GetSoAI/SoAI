/* SoAI - Tasks feature task operation API controller [frontend/assets/ts/features/tasks/taskmanager/TaskOperationApiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskLocalOperationUpdate, TaskOperationEntry, TaskOperationFilter, TaskOperationListener, TaskOperationMeta, TaskOperationsApi } from '@core/tasks/protocols.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { filterTaskOperations } from '@features/tasks/taskmanager/operationFiltering.ts';
import type { TaskOperationCancellationController } from '@features/tasks/taskmanager/TaskOperationCancellationController.ts';
import type { TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface TaskOperationApiControllerDependencies {
    store: TaskManagerStoreApi;
    cancellation: TaskOperationCancellationController;
}

class TaskOperationApiController implements TaskOperationsApi {
    readonly #store: TaskManagerStoreApi;
    readonly #cancellation: TaskOperationCancellationController;

    constructor(dependencies: TaskOperationApiControllerDependencies) {
        this.#store = dependencies.store;
        this.#cancellation = dependencies.cancellation;
    }

    getOperations(filter: TaskOperationFilter = {}): TaskOperationEntry[] {
        const operations = this.#cancellation.mergeLocalOperationMeta(this.#store.getActiveOperations());
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
        await this.#cancellation.cancelOperationById(operationId);
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
        if (update.cancelable === false) {
            meta['cancelable'] = false;
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
        this.#cancellation.registerLocalOperation(operationId, update.cancelable !== false, update.cancel, localOperation);
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
            this.#cancellation.removeLocalOperationState(operationId);
        }
    }

    removeLocalOperation(operationId: string): void {
        const operation = this.#store.getOperationById(operationId);
        const shouldRemoveStoreOperation = operation?.isLocal === true;
        this.#cancellation.removeLocalOperationState(operationId);
        if (shouldRemoveStoreOperation) {
            this.#store.removeOperationById(operationId);
        } else if (operation) {
            this.#store.upsertOperation(operation);
        }
    }

    #buildLocalOperationMeta(meta: TaskOperationMeta): TaskOperationMeta {
        const localMeta: TaskOperationMeta = {};
        for (const key of ['plugin', 'pluginName', 'convId', 'ownerType', 'ownerId', 'displayName', 'cancelable']) {
            const value = meta[key];
            if (value !== undefined && value !== null) {
                localMeta[key] = value;
            }
        }
        return localMeta;
    }
}

export { TaskOperationApiController };
