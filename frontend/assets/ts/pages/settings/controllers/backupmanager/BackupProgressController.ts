/* SoAI - Settings backup task progress ownership [frontend/assets/ts/pages/settings/controllers/backupmanager/BackupProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { AcceptedPowerActionResponse } from '@core/api/contracts/powerContracts.ts';
import type { BackupOperationState } from '@core/settings/contracts.ts';
import { parseBackupCompletionPayload, parseBackupProgressPayload } from '@pages/settings/controllers/backupmanager/mappers.ts';
import { resolveBackupFailureNotification, resolveBackupProgressLabel, resolveBackupSuccessNotification } from '@pages/settings/controllers/backupmanager/backupOperationMessagesController.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { OperationType } from '@features/overlays/public.ts';
import type { StreamActionResult } from '@core/realtime/streammanager/types.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';

interface BackupProgressHost extends PageFeedbackOwnerHost {
    getBackupOperation: () => BackupOperationState | null;
    setBackupOperation: (operation: BackupOperationState | null) => void;
    trackAcceptedTask: (taskId: string, options: { handlers: StreamActionHandlers; operation: { type: string } }) => StreamActionResult;
    restartApplication: () => Promise<AcceptedPowerActionResponse>;
    showRestartOverlay: (value: OperationType) => void;
}

interface BackupProgressDependencies {
    host: BackupProgressHost;
    renderProgress: () => void;
    requestReload: () => Promise<void>;
}

class BackupProgressController {
    readonly #host: BackupProgressHost;
    readonly #renderProgress: () => void;
    readonly #requestReload: () => Promise<void>;
    readonly #trackedTaskIds = new Set<string>();

    constructor({ host, renderProgress, requestReload }: BackupProgressDependencies) {
        this.#host = host;
        this.#renderProgress = renderProgress;
        this.#requestReload = requestReload;
    }

    track(operation: BackupOperationState): void {
        const existingOperation = this.#host.getBackupOperation();
        if (existingOperation && existingOperation.taskId !== operation.taskId) {
            throw new Error(`Cannot track backup task ${operation.taskId} while ${existingOperation.taskId} is active`);
        }
        this.#host.setBackupOperation(operation);
        this.#renderProgress();
        if (this.#trackedTaskIds.has(operation.taskId)) {
            return;
        }
        this.#trackedTaskIds.add(operation.taskId);
        try {
            const taskHandle = this.#host.trackAcceptedTask(operation.taskId, {
                operation: { type: `backup-${operation.type}` },
                handlers: {
                    onProgress: (data): void => this.#handleBackupProgress(data),
                    onComplete: (data): void => this.#handleBackupComplete(data),
                    onStreamError: (data): void => this.#handleBackupComplete(data),
                    onError: (error): void => this.#handleTrackingError(operation, ensureError(error))
                }
            });
            terminateHandledPromise(
                taskHandle.finished.finally(() => {
                    this.#trackedTaskIds.delete(operation.taskId);
                })
            );
        } catch (trackingError) {
            this.#trackedTaskIds.delete(operation.taskId);
            throw ensureError(trackingError);
        }
    }

    clear(): void {
        this.#host.setBackupOperation(null);
        this.#renderProgress();
    }

    #handleBackupProgress(data: JsonValue): void {
        const operation = this.#host.getBackupOperation();
        if (!operation) {
            return;
        }

        const payload = parseBackupProgressPayload(data);
        if (!payload) {
            return;
        }
        if (payload.taskId !== operation.taskId) {
            return;
        }

        this.#host.setBackupOperation({
            ...operation,
            progress: payload.percent,
            message: resolveBackupProgressLabel(operation.type)
        });
        if (payload.message) {
            errorHandler.debug('Settings', 'Backup task progress detail', { taskId: payload.taskId, message: payload.message });
        }
        this.#renderProgress();
    }

    #handleBackupComplete(data: JsonValue): void {
        const operation = this.#host.getBackupOperation();
        if (!operation) {
            return;
        }

        const payload = parseBackupCompletionPayload(data);
        if (!payload) {
            return;
        }
        if (payload.taskId !== operation.taskId) {
            return;
        }

        this.#trackedTaskIds.delete(operation.taskId);
        this.clear();

        if (payload.success) {
            this.#host.feedback.show(resolveBackupSuccessNotification(operation.type), 'success');
        } else {
            if (payload.message) {
                errorHandler.warn('Settings', 'Backup task reported failure', { taskId: payload.taskId, message: payload.message });
            }
            this.#host.feedback.show(resolveBackupFailureNotification(operation.type), 'error');
        }
        if (operation.type === 'restore') {
            void this.#host.restartApplication().catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.warn('Settings', 'Restart application after backup restore failed', runtimeError);
            });
            this.#host.showRestartOverlay('restore-backup');
            return;
        }
        this.#requestReloadSafely();
    }

    #handleTrackingError(operation: BackupOperationState, runtimeError: Error): void {
        this.#trackedTaskIds.delete(operation.taskId);
        if (this.#host.getBackupOperation()?.taskId !== operation.taskId) {
            return;
        }
        this.clear();
        this.#host.feedback.show(resolveBackupFailureNotification(operation.type), 'error');
        this.#requestReloadSafely();
        errorHandler.handleError(runtimeError, { context: `settings:${operation.type}BackupTracking` });
    }

    #requestReloadSafely(): void {
        void this.#requestReload().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('Settings', 'Backup manager reload failed', runtimeError);
        });
    }
}

export { BackupProgressController };
