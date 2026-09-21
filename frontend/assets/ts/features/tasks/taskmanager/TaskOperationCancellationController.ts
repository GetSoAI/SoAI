/* SoAI - Tasks feature task operation cancellation controller [frontend/assets/ts/features/tasks/taskmanager/TaskOperationCancellationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { isTerminalTaskStatus } from '@core/tasks/operationPayloads.ts';
import type { TaskOperationEntry } from '@core/tasks/protocols.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { CancellationBatchSummary, OperationEntry, TaskManagerStoreApi, TaskManagerStreamManager, TaskOperationCancellationOwner } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface TaskOperationCancellationControllerDependencies {
    store: TaskManagerStoreApi;
    stream: TaskManagerStreamManager;
    showNotification: (message: string, type: NotificationType) => void;
}

type OperationCancellationOutcome = 'requested' | 'alreadyTerminal' | 'skipped';

interface OperationCancellationAttempt {
    outcome: OperationCancellationOutcome | 'failed';
    error: Error | null;
    started: boolean;
}

interface InFlightCancellation {
    targetId: string;
    localCancel: (() => void | Promise<void>) | null;
    request: Promise<OperationCancellationOutcome>;
    resolve: (outcome: OperationCancellationOutcome) => void;
}

class TaskOperationCancellationController implements TaskOperationCancellationOwner {
    readonly #store: TaskManagerStoreApi;
    readonly #stream: TaskManagerStreamManager;
    readonly #showNotification: TaskOperationCancellationControllerDependencies['showNotification'];
    readonly #localCancelHandlers = new Map<string, () => void | Promise<void>>();
    readonly #localOperationMeta = new Map<string, TaskOperationEntry>();
    readonly #inFlightCancellations = new Map<string, InFlightCancellation>();

    constructor(dependencies: TaskOperationCancellationControllerDependencies) {
        this.#store = dependencies.store;
        this.#stream = dependencies.stream;
        this.#showNotification = dependencies.showNotification;
    }

    async cancelOperationById(operationId: string): Promise<void> {
        if (!isString(operationId) || !operationId.trim()) {
            return;
        }
        const normalizedOperationId = operationId.trim();
        const operation = this.#store.getOperationById(normalizedOperationId);
        if (!operation) {
            this.removeLocalOperationState(normalizedOperationId);
            return;
        }
        await this.cancelOperation(operation);
    }

    async cancelOperation(operation: OperationEntry): Promise<void> {
        if (!operation || !isObject(operation)) {
            throw new Error('TaskManager requires an operation to cancel');
        }
        const operationId = readRequiredTrimmedStringValue(operation.id, 'Operation identifier is required for cancellation');
        const current = this.#store.getOperationById(operationId);
        if (!current || current.cancelable !== true) {
            return;
        }
        const attempt = this.#getOrStartCancellation(current);
        try {
            const outcome = await attempt.request;
            if (attempt.started && outcome === 'requested') {
                this.#showNotification(i18n.plural('taskManager.notifications.cancelOperationsSuccess', 1, { count: 1 }), 'success');
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (attempt.started) {
                errorHandler.warn('TaskManager', 'Task cancellation request failed', runtimeError);
                this.#showNotification(i18n.t('taskManager.notifications.cancelOperationFailed'), 'error');
            }
            throw runtimeError;
        }
    }

    async cancelOperations(operations: readonly OperationEntry[]): Promise<CancellationBatchSummary> {
        const attempts = await Promise.all(operations.map((operation) => this.#runCancellationAttempt(operation)));
        const summary: CancellationBatchSummary = { requestedCount: 0, alreadyTerminalCount: 0, failedCount: 0 };
        const notificationSummary: CancellationBatchSummary = { requestedCount: 0, alreadyTerminalCount: 0, failedCount: 0 };
        const failures: Error[] = [];
        for (const attempt of attempts) {
            if (attempt.outcome === 'requested') summary.requestedCount += 1;
            if (attempt.outcome === 'alreadyTerminal') summary.alreadyTerminalCount += 1;
            if (attempt.outcome === 'failed') summary.failedCount += 1;
            if (!attempt.started) continue;
            if (attempt.outcome === 'requested') notificationSummary.requestedCount += 1;
            if (attempt.outcome === 'alreadyTerminal') notificationSummary.alreadyTerminalCount += 1;
            if (attempt.outcome === 'failed') notificationSummary.failedCount += 1;
            if (attempt.error) failures.push(attempt.error);
        }
        if (failures.length > 0) {
            errorHandler.warn('TaskManager', 'One or more task cancellation requests failed', new AggregateError(failures, 'Task cancellation request batch failed'));
        }
        this.#notifyCancellationSummary(notificationSummary, operations.length);
        return summary;
    }

    reset(): void {
        const inFlightCancellations = [...this.#inFlightCancellations.values()];
        this.#inFlightCancellations.clear();
        this.#localCancelHandlers.clear();
        this.#localOperationMeta.clear();
        for (const cancellation of inFlightCancellations) {
            cancellation.resolve('skipped');
        }
    }

    registerLocalOperation(operationId: string, cancelable: boolean, cancel: (() => void | Promise<void>) | undefined, localOperation: TaskOperationEntry): void {
        if (cancelable && isFunction(cancel)) {
            this.#localCancelHandlers.set(operationId, cancel);
        } else {
            this.#localCancelHandlers.delete(operationId);
        }
        this.#localOperationMeta.set(operationId, localOperation);
    }

    removeLocalOperationState(operationId: string): void {
        this.#localCancelHandlers.delete(operationId);
        this.#localOperationMeta.delete(operationId);
    }

    mergeLocalOperationMeta(operations: readonly TaskOperationEntry[]): TaskOperationEntry[] {
        this.#pruneLocalOperationState(operations);
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
                cancelable: localMeta.cancelable === false ? false : operation.cancelable === true || localMeta.cancelable === true
            };
        });
    }

    async #runCancellationAttempt(operation: OperationEntry): Promise<OperationCancellationAttempt> {
        if (!operation || !isObject(operation)) {
            return { outcome: 'failed', error: new Error('TaskManager requires an operation to cancel'), started: true };
        }
        if (!isString(operation.id) || !operation.id.trim()) {
            return { outcome: 'failed', error: new Error('Operation identifier is required for cancellation'), started: true };
        }
        const attempt = this.#getOrStartCancellation(operation);
        return attempt.request.then(
            (outcome) => ({ outcome, error: null, started: attempt.started }),
            (error) => ({ outcome: 'failed', error: ensureError(error), started: attempt.started })
        );
    }

    #getOrStartCancellation(operation: OperationEntry): { request: Promise<OperationCancellationOutcome>; started: boolean } {
        if (!operation || !isObject(operation)) {
            throw new Error('TaskManager requires an operation to cancel');
        }
        const operationId = readRequiredTrimmedStringValue(operation.id, 'Operation identifier is required for cancellation');
        const targetId = this.#resolveCancellationTarget(operation, operationId);
        const localCancel = this.#localCancelHandlers.get(operationId) ?? null;
        const existing = this.#inFlightCancellations.get(operationId);
        if (existing && existing.targetId === targetId && existing.localCancel === localCancel) {
            return { request: existing.request, started: false };
        }
        const request = createDeferred<OperationCancellationOutcome>();
        const inFlight: InFlightCancellation = { targetId, localCancel, request: request.promise, resolve: request.resolve };
        this.#inFlightCancellations.set(operationId, inFlight);
        void this.#executeCancellationRequest(operationId, targetId, localCancel, request, inFlight).catch((error) => {
            errorHandler.error('TaskManager', 'Task cancellation execution failed', ensureError(error));
        });
        return { request: request.promise, started: true };
    }

    async #executeCancellationRequest(operationId: string, targetId: string, localCancel: (() => void | Promise<void>) | null, request: ReturnType<typeof createDeferred<OperationCancellationOutcome>>, inFlight: InFlightCancellation): Promise<void> {
        try {
            request.resolve(await this.#requestOperationCancellation(operationId, targetId, localCancel, inFlight));
        } catch (error) {
            request.reject(ensureError(error));
        } finally {
            if (this.#inFlightCancellations.get(operationId) === inFlight) {
                this.#inFlightCancellations.delete(operationId);
            }
        }
    }

    async #requestOperationCancellation(operationId: string, targetId: string, localCancel: (() => void | Promise<void>) | null, inFlight: InFlightCancellation): Promise<OperationCancellationOutcome> {
        if (this.#inFlightCancellations.get(operationId) !== inFlight) return 'skipped';
        const current = this.#store.getOperationById(operationId);
        if (!current) return 'alreadyTerminal';
        const currentMeta = isObject(current.meta) ? current.meta : {};
        if (isTerminalTaskStatus(currentMeta['taskStatus'])) {
            this.#store.removeOperationById(operationId);
            return 'alreadyTerminal';
        }
        if (current.cancelable !== true) return 'skipped';
        if (!this.#isSameCancellationTarget(current, targetId)) return 'skipped';
        if ((this.#localCancelHandlers.get(operationId) ?? null) !== localCancel) return 'skipped';
        if (localCancel) {
            await localCancel();
            return this.#markLocalCancellationAccepted(operationId, targetId, localCancel, inFlight) ? 'requested' : 'skipped';
        }
        const cancellation = await this.#stream.tasks.requestTaskCancellation(targetId, getWebUiUserCancellationReason());
        return this.#applyRemoteCancellationResult(operationId, targetId, cancellation.taskId, cancellation.status, inFlight) ? 'requested' : 'skipped';
    }

    #markLocalCancellationAccepted(operationId: string, targetId: string, localCancel: () => void | Promise<void>, inFlight: InFlightCancellation): boolean {
        if (this.#inFlightCancellations.get(operationId) !== inFlight) return false;
        if (this.#localCancelHandlers.get(operationId) !== localCancel) return false;
        const current = this.#store.getOperationById(operationId);
        if (!current || !this.#isSameCancellationTarget(current, targetId)) return false;
        const meta = isObject(current.meta) ? current.meta : {};
        const localMeta = this.#localOperationMeta.get(operationId);
        if (localMeta) localMeta.cancelable = false;
        this.#store.upsertOperation({ ...current, cancelable: false, meta: { ...meta, cancelable: false } });
        return true;
    }

    #applyRemoteCancellationResult(operationId: string, targetId: string, responseTaskId: string, responseStatus: string, inFlight: InFlightCancellation): boolean {
        if (this.#inFlightCancellations.get(operationId) !== inFlight) return false;
        const current = this.#store.getOperationById(operationId);
        if (!current || !this.#isSameCancellationTarget(current, targetId)) return false;
        const currentMeta = isObject(current.meta) ? current.meta : {};
        if (isTerminalTaskStatus(currentMeta['taskStatus']) || isTerminalTaskStatus(responseStatus)) {
            this.#store.removeOperationById(operationId);
            return true;
        }
        const normalizedTaskId = isString(responseTaskId) && responseTaskId.trim() ? responseTaskId.trim() : targetId;
        this.#store.upsertOperation({ ...current, cancelable: false, meta: { ...currentMeta, cancelable: false, taskId: normalizedTaskId, taskStatus: responseStatus } });
        return true;
    }

    #resolveCancellationTarget(operation: OperationEntry, operationId: string): string {
        const meta = isObject(operation.meta) ? operation.meta : {};
        const taskId = meta['taskId'];
        return isString(taskId) && taskId.trim() ? taskId.trim() : operationId;
    }

    #isSameCancellationTarget(operation: OperationEntry, targetId: string): boolean {
        const operationId = readRequiredTrimmedStringValue(operation.id, 'Operation identifier is required for cancellation');
        return this.#resolveCancellationTarget(operation, operationId) === targetId;
    }

    #notifyCancellationSummary(summary: CancellationBatchSummary, totalCount: number): void {
        if (summary.failedCount > 0 && summary.requestedCount > 0) {
            this.#showNotification(i18n.t('taskManager.notifications.cancelOperationsPartial', { requestedCount: summary.requestedCount, totalCount, failedCount: summary.failedCount }), 'warning');
            return;
        }
        if (summary.failedCount > 0) {
            this.#showNotification(i18n.plural('taskManager.notifications.cancelOperationsFailed', summary.failedCount, { count: summary.failedCount }), 'error');
            return;
        }
        if (summary.requestedCount > 0) {
            this.#showNotification(i18n.plural('taskManager.notifications.cancelOperationsSuccess', summary.requestedCount, { count: summary.requestedCount }), 'success');
            return;
        }
        if (summary.alreadyTerminalCount > 0) this.#showNotification(i18n.t('taskManager.notifications.cancelOperationsAlreadyFinished'), 'info');
    }

    #pruneLocalOperationState(operations: readonly TaskOperationEntry[]): void {
        if (this.#localCancelHandlers.size === 0 && this.#localOperationMeta.size === 0) return;
        const activeOperationIds = new Set(operations.map((operation) => operation.id));
        for (const operationId of this.#localCancelHandlers.keys()) {
            if (!activeOperationIds.has(operationId)) this.#localCancelHandlers.delete(operationId);
        }
        for (const operationId of this.#localOperationMeta.keys()) {
            if (!activeOperationIds.has(operationId)) this.#localOperationMeta.delete(operationId);
        }
    }
}

export { TaskOperationCancellationController };
