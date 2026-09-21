/* SoAI - Tasks feature task manager actions [frontend/assets/ts/features/tasks/taskmanager/TaskManagerActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { stopAllPluginsActionPath, stopPluginActionPath } from '@core/api/endpoints/uiPaths.ts';
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
import type { OperationMeta, TaskManagerApi, TaskManagerStoreApi, TaskManagerStreamManager, TaskOperationCancellationOwner } from '@features/tasks/taskmanager/taskManagerTypes.ts';

const ensureRequiredString = <T>(value: T, errorMessage: string): string => {
    return readRequiredTrimmedStringValue(value, errorMessage);
};

interface TaskManagerActionsDependencies {
    apiClient: TaskManagerApi;
    stream: TaskManagerStreamManager;
    store: TaskManagerStoreApi;
    operationCancellation: TaskOperationCancellationOwner;
    showNotification: (message: string, type: NotificationType) => void;
    hidePanel: () => void;
}

class TaskManagerActions {
    #dependencies: TaskManagerActionsDependencies;

    constructor(dependencies: TaskManagerActionsDependencies) {
        this.#dependencies = dependencies;
    }

    async stopPlugin(pluginName: string): Promise<void> {
        const normalized = ensureRequiredString(pluginName, 'TaskManager stopPlugin requires a plugin name');
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
        const stoppable = store.getStoppablePlugins();
        const cancelable = store.getCancelableOperations();
        const stopCount = stoppable.length;
        const cancelCount = cancelable.length;

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

        const cancellationPromise = this.#dependencies.operationCancellation.cancelOperations(cancelable);
        const pluginStopPromise =
            stopCount > 0
                ? handleApiResult(this.#dependencies.apiClient.post(stopAllPluginsActionPath(), null), {
                      boundaryName: 'TaskManager',
                      notifyOnSuccess: true,
                      notifySuccessMessage: i18n.t('taskManager.notifications.stopAllSuccess'),
                      notifyOnError: true,
                      notifyErrorMessage: i18n.t('taskManager.notifications.stopAllFailed')
                  })
                : Promise.resolve();
        const [cancellationSummary, pluginsStopped] = await Promise.all([
            cancellationPromise,
            pluginStopPromise.then(
                () => true,
                () => false
            )
        ]);
        if (pluginsStopped && cancellationSummary.failedCount === 0) {
            this.#dependencies.hidePanel();
        }
    }

    async handleStopButtonClick(button: HTMLElement): Promise<void> {
        if (!button) {
            throw new Error('TaskManager requires a valid button element for stop handler');
        }
        const name = ensureRequiredString(dom.getData(button, 'plugin'), 'TaskManager stop button missing plugin name');
        const key = ensureRequiredString(dom.getData(button, 'pluginKey'), 'TaskManager stop button missing plugin key');
        const canCancel = String(dom.getData(button, 'canCancel')).trim() === 'true';

        if (canCancel) {
            await this.cancelOperationsForPlugin(key);
            return;
        }
        await this.stopPlugin(name);
    }

    async cancelOperationsForPlugin(key: string): Promise<void> {
        const normalized = ensureRequiredString(key, 'TaskManager requires a plugin key to cancel operations');
        const operations = this.#dependencies.store.getCancelableOperationsForPluginKey(normalized);
        await this.#dependencies.operationCancellation.cancelOperations(operations);
    }

    async #runTaskAction(endpoint: string, operation: OperationMeta, successMessage: string, errorMessage: string): Promise<void> {
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
            this.#reportTaskActionFailure(runtimeError, errorMessage);
            throw runtimeError;
        }
        const record = isObject(result) ? result : null;
        if (record?.['cancelled'] === true) {
            return;
        }
        if (record?.['success'] === false) {
            const diagnosticMessage = toTrimmedString(record?.['message']) || 'Task action failed';
            const runtimeError = new Error(diagnosticMessage);
            this.#reportTaskActionFailure(runtimeError, errorMessage);
            throw runtimeError;
        }
        this.#dependencies.showNotification(successMessage, 'success');
    }

    #reportTaskActionFailure(error: Error, userMessage: string): void {
        errorHandler.error('TaskManager', 'Task action failed', error);
        this.#dependencies.showNotification(userMessage, 'error');
    }
}

export { TaskManagerActions };
export type { TaskManagerActionsDependencies };
