/* SoAI - Tasks feature task manager actions [frontend/assets/ts/features/tasks/taskmanager/TaskManagerActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stopPluginActionPath } from '@core/api/endpoints/uiPaths.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { OperationMeta, TaskManagerStoreApi, TaskManagerStreamManager, TaskOperationCancellationOwner } from '@features/tasks/taskmanager/taskManagerTypes.ts';
import { resolveStopAllTargets } from '@features/tasks/taskmanager/service.ts';

interface TaskManagerActionsDependencies {
    stream: TaskManagerStreamManager;
    store: TaskManagerStoreApi;
    operationCancellation: TaskOperationCancellationOwner;
    showNotification: (message: string, type: NotificationType) => void;
}

class TaskManagerActions {
    #dependencies: TaskManagerActionsDependencies;

    constructor(dependencies: TaskManagerActionsDependencies) {
        this.#dependencies = dependencies;
    }

    async stopPlugin(pluginName: string): Promise<void> {
        const normalized = readRequiredTrimmedStringValue(pluginName, 'TaskManager stopPlugin requires a plugin name');
        await this.#runTaskAction(
            stopPluginActionPath(normalized),
            {
                type: 'background-job',
                pluginName: normalized
            },
            i18n.t('taskManager.notifications.pluginStopped', { pluginName: normalized }),
            i18n.t('taskManager.notifications.stopFailed', { pluginName: normalized })
        );
    }

    async stopAllPlugins(): Promise<void> {
        const store = this.#dependencies.store;
        const targets = resolveStopAllTargets(store);
        const stopCount = targets.plugins.length;
        const cancelCount = targets.operations.length;

        if (stopCount === 0 && cancelCount === 0) {
            this.#dependencies.showNotification(i18n.t('taskManager.messages.noStoppablePlugins'), 'warning');
            return;
        }

        const messageParts: string[] = [];
        if (stopCount > 0) {
            messageParts.push(i18n.plural('taskManager.confirmations.stopAllMessage', stopCount, { count: stopCount }));
        }
        if (cancelCount > 0) {
            messageParts.push(i18n.plural('taskManager.confirmations.cancelOperationsMessage', cancelCount, { count: cancelCount }));
        }

        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('taskManager.actions.stopAll'),
            message: messageParts.join('<br><br>'),
            messageAllowHTML: true,
            confirmText: i18n.t('taskManager.confirmations.stopAllButton'),
            cancelText: i18n.t('common.cancel')
        });
        if (!confirmed) {
            return;
        }

        const approvedPluginKeys = new Set(targets.plugins.map((plugin) => store.getPluginKey(plugin)));
        const currentTargets = resolveStopAllTargets(store);
        const pluginNames = currentTargets.plugins.filter((plugin) => approvedPluginKeys.has(store.getPluginKey(plugin))).map((plugin) => readRequiredTrimmedStringValue(plugin.name || plugin.identifier || plugin.plugin, 'TaskManager stop-all requires a plugin name'));
        const cancellationSummary = await this.#dependencies.operationCancellation.cancelOperations(targets.operations);
        if (pluginNames.length > 0) {
            const results = await Promise.allSettled(pluginNames.map((pluginName) => this.#runTaskAction(stopPluginActionPath(pluginName), { type: 'background-job', pluginName }, i18n.t('taskManager.notifications.pluginStopped', { pluginName }), i18n.t('taskManager.notifications.stopFailed', { pluginName }), false)));
            if (results.some((result) => result.status === 'rejected')) {
                this.#dependencies.showNotification(i18n.t('taskManager.notifications.stopAllFailed'), 'error');
            } else if (cancellationSummary.failedCount === 0 && results.every((result) => result.status === 'fulfilled' && result.value)) {
                this.#dependencies.showNotification(i18n.t('taskManager.notifications.stopAllSuccess'), 'success');
            }
        }
    }

    async handleStopButtonClick(button: HTMLElement): Promise<void> {
        if (!button) {
            throw new Error('TaskManager requires a valid button element for stop handler');
        }
        const name = readRequiredTrimmedStringValue(dom.getData(button, 'plugin'), 'TaskManager stop button missing plugin name');
        const key = readRequiredTrimmedStringValue(dom.getData(button, 'pluginKey'), 'TaskManager stop button missing plugin key');
        const canCancel = String(dom.getData(button, 'canCancel')).trim() === 'true';

        if (canCancel) {
            await this.cancelOperationsForPlugin(key);
            return;
        }
        await this.stopPlugin(name);
    }

    async cancelOperationsForPlugin(key: string): Promise<void> {
        const normalized = readRequiredTrimmedStringValue(key, 'TaskManager requires a plugin key to cancel operations');
        const operations = this.#dependencies.store.getCancelableOperationsForPluginKey(normalized);
        await this.#dependencies.operationCancellation.cancelOperations(operations);
    }

    async #runTaskAction(endpoint: string, operation: OperationMeta, successMessage: string, errorMessage: string, notify = true): Promise<boolean> {
        await ensureStreamManagerReady(this.#dependencies.stream.resources, { allowDiscovery: true });
        let result: JsonValue | null | undefined;
        try {
            const handle = this.#dependencies.stream.tasks.taskAction(endpoint, {
                method: 'POST',
                operation
            });
            result = await handle.finished;
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#reportTaskActionFailure(runtimeError, errorMessage, notify);
            throw runtimeError;
        }
        const record = isObject(result) ? result : null;
        if (record?.['cancelled'] === true) {
            return false;
        }
        if (record?.['success'] === false) {
            const diagnosticMessage = toTrimmedString(record?.['message']) || 'Task action failed';
            const runtimeError = new Error(diagnosticMessage);
            this.#reportTaskActionFailure(runtimeError, errorMessage, notify);
            throw runtimeError;
        }
        if (notify) this.#dependencies.showNotification(successMessage, 'success');
        return true;
    }

    #reportTaskActionFailure(error: Error, userMessage: string, notify: boolean): void {
        errorHandler.error('TaskManager', 'Task action failed', error);
        if (notify) this.#dependencies.showNotification(userMessage, 'error');
    }
}

export { TaskManagerActions };
export type { TaskManagerActionsDependencies };
