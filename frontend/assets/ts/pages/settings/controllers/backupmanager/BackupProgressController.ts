/* SoAI - Settings backup task progress ownership [frontend/assets/ts/pages/settings/controllers/backupmanager/BackupProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
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
    showRestartOverlay: (value: OperationType) => void;
}

interface BackupProgressDependencies {
    host: BackupProgressHost;
    renderProgress: () => void;
    requestReload: () => Promise<void>;
}

interface BackupTaskTracking {
    taskId: string;
    handle: StreamActionResult | null;
}

class BackupProgressController {
    readonly #host: BackupProgressHost;
    readonly #renderProgress: () => void;
    readonly #requestReload: () => Promise<void>;
    #tracking: BackupTaskTracking | null = null;
    #automaticRecoveryAttempted = false;

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
        if (this.#tracking?.taskId === operation.taskId) {
            return;
        }
        const retainedOperation = existingOperation ?? operation;
        const trackingState = retainedOperation.tracking ?? { status: 'current', updatedAtMs: serverEpochMs() };
        this.#host.setBackupOperation({ ...retainedOperation, tracking: { ...trackingState, status: trackingState.status === 'unavailable' ? 'recovering' : trackingState.status } });
        const tracking: BackupTaskTracking = { taskId: operation.taskId, handle: null };
        this.#tracking = tracking;
        this.#renderProgress();
        try {
            const taskHandle = this.#host.trackAcceptedTask(operation.taskId, {
                operation: { type: `backup-${operation.type}` },
                handlers: {
                    onProgress: (data): void => this.#handleBackupProgress(tracking, data),
                    onComplete: (data): void => this.#handleBackupComplete(tracking, data),
                    onStreamError: (data): void => this.#handleBackupComplete(tracking, data),
                    onError: (error): void => this.#handleTrackingError(tracking, ensureError(error))
                }
            });
            tracking.handle = taskHandle;
            terminateHandledPromise(
                taskHandle.finished.finally(() => {
                    if (this.#tracking === tracking) {
                        this.#handleTrackingError(tracking, new Error('Backup watcher ended without a terminal task outcome'));
                    }
                })
            );
        } catch (trackingError) {
            this.#handleTrackingError(tracking, ensureError(trackingError));
        }
    }

    resume(): void {
        const operation = this.#host.getBackupOperation();
        if (operation && this.#tracking === null) {
            this.track(operation);
        }
    }

    clear(): void {
        const tracking = this.#tracking;
        this.#tracking = null;
        this.#automaticRecoveryAttempted = false;
        this.#host.setBackupOperation(null);
        tracking?.handle?.close?.();
        this.#renderProgress();
    }

    dispose(): void {
        const tracking = this.#tracking;
        this.#tracking = null;
        const operation = this.#host.getBackupOperation();
        if (operation?.tracking && operation.taskId === tracking?.taskId) {
            this.#host.setBackupOperation({ ...operation, tracking: { ...operation.tracking, status: 'recovering' } });
        }
        tracking?.handle?.close?.();
    }

    #handleBackupProgress(tracking: BackupTaskTracking, data: JsonValue): void {
        const operation = this.#host.getBackupOperation();
        if (!operation || this.#tracking !== tracking || operation.taskId !== tracking.taskId) {
            return;
        }

        const payload = parseBackupProgressPayload(data);
        if (!payload) {
            return;
        }
        if (payload.taskId !== operation.taskId) {
            return;
        }

        this.#automaticRecoveryAttempted = false;
        this.#host.setBackupOperation({
            ...operation,
            tracking: { status: 'current', updatedAtMs: serverEpochMs() },
            progress: payload.percent,
            message: resolveBackupProgressLabel(operation.type)
        });
        if (payload.message) {
            errorHandler.debug('Settings', 'Backup task progress detail', { taskId: payload.taskId, message: payload.message });
        }
        this.#renderProgress();
    }

    #handleBackupComplete(tracking: BackupTaskTracking, data: JsonValue): void {
        const operation = this.#host.getBackupOperation();
        if (!operation || this.#tracking !== tracking || operation.taskId !== tracking.taskId) {
            return;
        }

        const payload = parseBackupCompletionPayload(data);
        if (!payload) {
            return;
        }
        if (payload.taskId !== operation.taskId) {
            return;
        }

        if (isJsonObject(data) && (data['detached'] === true || data['status'] === 'detached')) {
            this.#handleTrackingError(tracking, new Error('Backup task snapshot is unavailable'));
            return;
        }
        this.clear();

        if (payload.success) {
            this.#host.feedback.show(resolveBackupSuccessNotification(operation.type), 'success');
        } else {
            if (payload.message) {
                errorHandler.warn('Settings', 'Backup task reported failure', { taskId: payload.taskId, message: payload.message });
            }
            this.#host.feedback.show(resolveBackupFailureNotification(operation.type), 'error');
        }
        if (operation.type === 'restore' && payload.success) {
            this.#host.showRestartOverlay('restore-backup');
            return;
        }
        this.#requestReloadSafely();
    }

    #handleTrackingError(tracking: BackupTaskTracking, runtimeError: Error): void {
        const operation = this.#host.getBackupOperation();
        if (!operation || this.#tracking !== tracking || operation.taskId !== tracking.taskId) {
            return;
        }
        this.#tracking = null;
        const shouldRecover = !this.#automaticRecoveryAttempted;
        this.#automaticRecoveryAttempted = true;
        this.#host.setBackupOperation({
            ...operation,
            tracking: { status: shouldRecover ? 'recovering' : 'unavailable', updatedAtMs: operation.tracking?.updatedAtMs ?? serverEpochMs() }
        });
        this.#renderProgress();
        errorHandler.warn('Settings', 'Backup task tracking lost', runtimeError);
        if (shouldRecover) {
            this.#requestReloadSafely();
        } else {
            this.#host.feedback.show(i18n.t('settings.availability.unavailable'), 'warning');
        }
    }

    #requestReloadSafely(): void {
        void this.#requestReload().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('Settings', 'Backup manager reload failed', runtimeError);
        });
    }
}

export { BackupProgressController };
